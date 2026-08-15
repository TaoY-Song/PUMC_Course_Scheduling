"""Scheduling APIs for the web backend."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.credit_manager import CreditManager, CreditRequirement
from core.scheduling.config import (
    CampusConflictMode as CoreCampusConflictMode,
    CreditConstraintMode as CoreCreditConstraintMode,
    SchedulingConfig,
)
from core.scheduling.models import ConflictInfo, ScheduleResult, ScheduleScore
from core.services.interfaces import ISchedulingService

from ..api.courses import _selected_course_to_dto
from ..dependencies import get_scheduling_service, get_web_session
from ..models.dto import (
    ApiResponse,
    CampusConflictMode as CampusConflictModeDTO,
    ConflictInfoDTO,
    CreditRequirementDTO,
    CreditConstraintMode as CreditConstraintModeDTO,
    ExecuteSchedulingRequest,
    ExecuteSchedulingResponse,
    ScheduleResultDTO,
    ScheduleScoreDTO,
    SchedulingConfigDTO,
    SchedulingTaskResultResponse,
    SchedulingTaskStatusResponse,
    TaskStatus as TaskStatusDTO,
)
from ..services.task_runtime import (
    SchedulingTaskRecord,
    TaskAlreadyRunningError,
    TaskStatus as RuntimeTaskStatus,
    get_task_runtime,
)
from ..state import WebSessionContext

router = APIRouter(tags=["scheduling"])
task_runtime = get_task_runtime()


def _to_config_dto(config: SchedulingConfig) -> SchedulingConfigDTO:
    return SchedulingConfigDTO(
        credit_constraint_mode=CreditConstraintModeDTO(config.credit_constraint_mode.value.upper()),
        campus_conflict_mode=CampusConflictModeDTO(config.campus_conflict_mode.value.upper()),
        campus_equivalence_groups=[list(group) for group in config.campus_equivalence_groups],
        max_solutions=min(config.max_solutions, 10),
        time_limit=config.max_solve_time_seconds,
        credit_overflow=config.max_credit_overflow,
    )


def _to_schedule_score_dto(score: ScheduleScore) -> ScheduleScoreDTO:
    return ScheduleScoreDTO(
        total_score=score.total_score,
        credit_match_score=score.credit_efficiency_score,
        time_quality_score=score.time_preference_score,
    )


def _to_conflict_dto(conflict: ConflictInfo) -> ConflictInfoDTO:
    return ConflictInfoDTO(
        course1_code=conflict.course1.code if conflict.course1 else "",
        course2_code=conflict.course2.code if conflict.course2 else "",
        conflict_type=conflict.conflict_type,
        description=conflict.description,
    )


def _to_result_dto(result: ScheduleResult) -> ScheduleResultDTO:
    return ScheduleResultDTO(
        id=result.schedule_id,
        selected_courses=[_selected_course_to_dto(course) for course in result.selected_courses],
        score=_to_schedule_score_dto(result.score),
        conflicts=[_to_conflict_dto(conflict) for conflict in result.conflicts],
        execution_time=result.solve_time_seconds,
    )


def _build_credit_snapshot(session: WebSessionContext) -> CreditManager:
    return session.clone_credit_manager_for_status()


def _to_task_status_dto(status: RuntimeTaskStatus) -> TaskStatusDTO:
    return TaskStatusDTO(status.value)


def _task_base_payload(record: SchedulingTaskRecord) -> Dict[str, object]:
    return {
        "task_id": record.task_id,
        "status": _to_task_status_dto(record.status),
        "message": record.message,
        "error_message": record.error_message,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "is_active": record.is_active,
        "is_finished": record.is_finished,
        "can_cancel": record.can_cancel,
        # 🔧 P1 修复：向前端暴露进度
        "percent": getattr(record, "percent", 0),
    }


def _to_execute_response(record: SchedulingTaskRecord, success: bool = True) -> ExecuteSchedulingResponse:
    return ExecuteSchedulingResponse(
        success=success,
        result=_to_result_dto(record.result) if record.result else None,
        **_task_base_payload(record),
    )


def _to_status_response(record: SchedulingTaskRecord, success: bool = True) -> SchedulingTaskStatusResponse:
    return SchedulingTaskStatusResponse(
        success=success,
        has_result=record.has_result,
        result=_to_result_dto(record.result) if record.result else None,
        **_task_base_payload(record),
    )


def _to_result_response(record: SchedulingTaskRecord, success: bool = True) -> SchedulingTaskResultResponse:
    return SchedulingTaskResultResponse(
        success=success,
        has_result=record.has_result,
        result=_to_result_dto(record.result) if record.result else None,
        **_task_base_payload(record),
    )


def _get_task_or_404(task_id: str) -> SchedulingTaskRecord:
    record = task_runtime.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return record


@router.get("/scheduling/config", response_model=SchedulingConfigDTO)
async def get_config(session: WebSessionContext = Depends(get_web_session)):
    return _to_config_dto(session.scheduling_config)


@router.post("/scheduling/config", response_model=ApiResponse)
async def configure_scheduling(
    config_dto: SchedulingConfigDTO,
    scheduling_service: ISchedulingService = Depends(get_scheduling_service),
    session: WebSessionContext = Depends(get_web_session),
):
    credit_mode = CoreCreditConstraintMode(config_dto.credit_constraint_mode.value.lower())
    campus_mode = CoreCampusConflictMode(config_dto.campus_conflict_mode.value.lower())

    next_config = SchedulingConfig(
        credit_constraint_mode=credit_mode,
        campus_conflict_mode=campus_mode,
        campus_equivalence_groups=tuple(
            tuple(dict.fromkeys(str(campus).strip() for campus in group if str(campus).strip()))
            for group in config_dto.campus_equivalence_groups
        ),
        max_solutions=config_dto.max_solutions,
        max_solve_time_seconds=config_dto.time_limit,
        max_credit_overflow=config_dto.credit_overflow,
    )
    validation_errors = next_config.validate()
    if validation_errors:
        raise HTTPException(status_code=422, detail="；".join(validation_errors))
    session.scheduling_config = next_config
    scheduling_service.configure(next_config)

    return ApiResponse(success=True, message="排课配置已更新")


@router.post("/scheduling/execute", response_model=ExecuteSchedulingResponse)
async def execute_scheduling(
    request: ExecuteSchedulingRequest,
    session: WebSessionContext = Depends(get_web_session),
):
    selected_course_ids = request.course_ids or None

    try:
        record = task_runtime.submit_task(session, selected_course_ids)
    except TaskAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _to_execute_response(record, success=True)


@router.get("/scheduling/status/{task_id}", response_model=SchedulingTaskStatusResponse)
async def get_scheduling_task_status(task_id: str):
    record = _get_task_or_404(task_id)
    return _to_status_response(record, success=True)


@router.get("/scheduling/result/{task_id}", response_model=SchedulingTaskResultResponse)
async def get_scheduling_task_result(task_id: str):
    record = _get_task_or_404(task_id)
    return _to_result_response(record, success=True)


@router.post("/scheduling/cancel/{task_id}", response_model=SchedulingTaskStatusResponse)
async def cancel_scheduling_task(task_id: str):
    existing = task_runtime.get_task(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    was_finished = existing.is_finished

    record = task_runtime.cancel_task(task_id)
    if record is None:  # 防御性处理：单进程运行时不应在两次读取间删除任务。
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_status_response(record, success=not was_finished)


@router.get("/scheduling/status")
async def get_scheduling_status_compat(session: WebSessionContext = Depends(get_web_session)):
    if session.current_task is not None:
        return {
            "status": session.current_task.status.value,
            "task_id": session.current_task.task_id,
            "message": session.current_task.message,
            "error_message": session.current_task.error_message,
            "updated_at": session.current_task.updated_at,
        }

    status = session.scheduling_service.get_status()
    return {"status": status.value}


@router.post("/scheduling/cancel", response_model=ApiResponse)
async def cancel_scheduling_compat(session: WebSessionContext = Depends(get_web_session)):
    if session.current_task is not None:
        if session.current_task.status == RuntimeTaskStatus.CANCEL_REQUESTED:
            return ApiResponse(success=True, message="取消请求已提交")
        if session.current_task.can_cancel:
            record = task_runtime.cancel_task(session.current_task.task_id)
            if record is not None:
                return ApiResponse(success=True, message=record.message)
        elif session.current_task.is_finished:
            return ApiResponse(success=False, message="当前任务已结束，无法取消")

    success = session.scheduling_service.cancel()
    return ApiResponse(success=success, message="排课已取消" if success else "取消失败")


@router.get("/scheduling/result", response_model=Optional[ScheduleResultDTO])
async def get_last_result(session: WebSessionContext = Depends(get_web_session)):
    if session.last_scheduling_result is None:
        return None
    return _to_result_dto(session.last_scheduling_result)


@router.get("/credits", response_model=List[CreditRequirementDTO])
async def get_credit_status(session: WebSessionContext = Depends(get_web_session)):
    credit_manager = _build_credit_snapshot(session)

    requirements: List[CreditRequirementDTO] = []
    for category, req in credit_manager.requirements.items():
        category_courses = []
        for selected_course in session.selected_courses.values():
            selected_category = selected_course.custom_category or selected_course.course.category
            if selected_category == category:
                category_courses.append(_selected_course_to_dto(selected_course))

        requirements.append(
            CreditRequirementDTO(
                category=category,
                required_credits=req.required_credits,
                completed_credits=req.completed_credits,
                remaining_credits=req.remaining_credits,
                is_completed=req.is_completed,
                courses=category_courses,
            )
        )

    return requirements


@router.post("/credits/settings", response_model=ApiResponse)
async def update_credit_requirements(
    requirements: Dict[str, float],
    session: WebSessionContext = Depends(get_web_session),
):
    for category, credits in requirements.items():
        if credits < 0:
            raise HTTPException(status_code=400, detail=f"学分要求不能为负数: {category}")
        if category not in session.credit_manager.requirements:
            session.credit_manager.requirements[category] = CreditRequirement(
                category_name=category,
                required_credits=credits,
            )
        else:
            session.credit_manager.set_required_credits(category, credits)

    return ApiResponse(success=True, message="学分要求已更新")


@router.get("/credits/settings", response_model=Dict[str, float])
async def get_credit_requirements(session: WebSessionContext = Depends(get_web_session)):
    return {
        category: req.required_credits
        for category, req in session.credit_manager.requirements.items()
    }
