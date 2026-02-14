"""
排课算法API
提供排课配置、执行、状态查询等功能
"""
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..models.dto import (
    SchedulingConfigDTO, ExecuteSchedulingRequest, ExecuteSchedulingResponse,
    ScheduleResultDTO, ScheduleScoreDTO, ConflictInfoDTO, ApiResponse,
    SelectedCourseDTO, CreditRequirementDTO
)
from ..dependencies import get_scheduling_service, get_data_service
from ..api.courses import _storage, _selected_course_to_dto
from core.services.interfaces import ISchedulingService, IDataService
from core.scheduling.config import SchedulingConfig, CreditConstraintMode, CampusConflictMode

router = APIRouter(tags=["scheduling"])

_config: Optional[SchedulingConfig] = None
_last_result: Optional[dict] = None

@router.get("/scheduling/config", response_model=SchedulingConfigDTO)
async def get_config():
    """获取当前排课配置"""
    global _config
    if _config is None:
        _config = SchedulingConfig(max_solutions=10)
    
    credit_map = {"required": "REQUIRED", "optimal": "OPTIMAL"}
    campus_map = {"daily": "DAILY", "period": "PERIOD", "disabled": "DISABLED"}
    
    return SchedulingConfigDTO(
        credit_constraint_mode=credit_map.get(_config.credit_constraint_mode.value, "OPTIMAL"),
        campus_conflict_mode=campus_map.get(_config.campus_conflict_mode.value, "DAILY"),
        max_solutions=min(_config.max_solutions, 10),
        time_limit=_config.max_solve_time_seconds,
        credit_overflow_ratio=_config.max_credit_overflow_ratio,
        campus_transition_time=_config.min_campus_transfer_time
    )

@router.post("/scheduling/config", response_model=ApiResponse)
async def configure_scheduling(
    config_dto: SchedulingConfigDTO,
    scheduling_service: ISchedulingService = Depends(get_scheduling_service)
):
    """配置排课参数"""
    global _config
    
    credit_map = {"REQUIRED": "required", "OPTIMAL": "optimal"}
    campus_map = {"DAILY": "daily", "PERIOD": "period", "DISABLED": "disabled"}
    
    _config = SchedulingConfig(
        credit_constraint_mode=CreditConstraintMode(credit_map.get(config_dto.credit_constraint_mode, "optimal")),
        campus_conflict_mode=CampusConflictMode(campus_map.get(config_dto.campus_conflict_mode, "daily")),
        max_solutions=config_dto.max_solutions,
        max_solve_time_seconds=config_dto.time_limit,
        max_credit_overflow_ratio=config_dto.credit_overflow_ratio,
        min_campus_transfer_time=config_dto.campus_transition_time
    )
    
    scheduling_service.configure(_config)
    
    return ApiResponse(success=True, message="配置已更新")

@router.post("/scheduling/execute", response_model=ExecuteSchedulingResponse)
async def execute_scheduling(
    request: ExecuteSchedulingRequest,
    scheduling_service: ISchedulingService = Depends(get_scheduling_service)
):
    """执行排课算法"""
    global _config, _last_result
    
    if _config is None:
        _config = SchedulingConfig()
        scheduling_service.configure(_config)
    
    try:
        selected_courses = []
        if request.course_ids:
            for cid in request.course_ids:
                if cid in _storage["selected_courses"]:
                    selected_courses.append(_storage["selected_courses"][cid])
        else:
            selected_courses = list(_storage["selected_courses"].values())
        
        if not selected_courses:
            return ExecuteSchedulingResponse(
                success=False,
                error_message="没有要排课的课程"
            )
        
        result = scheduling_service.execute(selected_courses)
        
        _last_result = {
            "courses": result.selected_courses,
            "score": result.score,
            "conflicts": result.conflicts,
            "execution_time": result.solve_time_seconds
        }
        
        return ExecuteSchedulingResponse(
            success=True,
            result=ScheduleResultDTO(
                id="result_001",
                selected_courses=[_selected_course_to_dto(c) for c in result.selected_courses],
                score=ScheduleScoreDTO(
                    total_score=result.score.total_score,
                    credit_match_score=result.score.credit_efficiency_score,
                    time_quality_score=result.score.time_preference_score
                ),
                conflicts=[
                    ConflictInfoDTO(
                        course1_code=c.course1.code if c.course1 else "",
                        course2_code=c.course2.code if c.course2 else "",
                        conflict_type=c.conflict_type,
                        description=c.description
                    ) for c in result.conflicts
                ],
                execution_time=result.solve_time_seconds
            )
        )
        
    except Exception as e:
        return ExecuteSchedulingResponse(
            success=False,
            error_message=str(e)
        )

@router.get("/scheduling/status")
async def get_scheduling_status(
    scheduling_service: ISchedulingService = Depends(get_scheduling_service)
):
    """获取排课状态"""
    status = scheduling_service.get_status()
    return {"status": status.value}

@router.post("/scheduling/cancel", response_model=ApiResponse)
async def cancel_scheduling(
    scheduling_service: ISchedulingService = Depends(get_scheduling_service)
):
    """取消排课"""
    success = scheduling_service.cancel()
    return ApiResponse(
        success=success,
        message="排课已取消" if success else "取消失败"
    )

@router.get("/scheduling/result", response_model=Optional[ScheduleResultDTO])
async def get_last_result():
    """获取最后一次排课结果"""
    global _last_result
    if _last_result is None:
        return None
    
    return ScheduleResultDTO(
        id="result_001",
        selected_courses=[_selected_course_to_dto(c) for c in _last_result["courses"]],
        score=ScheduleScoreDTO(
            total_score=_last_result["score"].total_score,
            credit_match_score=_last_result["score"].credit_efficiency_score,
            time_quality_score=_last_result["score"].time_preference_score
        ),
        conflicts=[
            ConflictInfoDTO(
                course1_code=c.course1.course_code,
                course2_code=c.course2.course_code,
                conflict_type=c.conflict_type,
                description=c.description
            ) for c in _last_result["conflicts"]
        ],
        execution_time=_last_result["execution_time"]
    )

@router.get("/credits", response_model=List[CreditRequirementDTO])
async def get_credit_status(
    data_service: IDataService = Depends(get_data_service)
):
    """获取学分完成情况"""
    from core.credit_manager import CreditManager
    
    credit_manager = CreditManager()
    
    for sc in _storage["selected_courses"].values():
        category = sc.custom_category or sc.course.category
        credit_manager.add_completed_credits(category, sc.course.credits)
    
    requirements = []
    for cat, req in credit_manager.requirements.items():
        requirements.append(CreditRequirementDTO(
            category=cat,
            required_credits=req.required_credits,
            completed_credits=req.completed_credits,
            remaining_credits=req.remaining_credits,
            is_completed=req.is_completed,
            courses=[
                _selected_course_to_dto(sc)
                for sc in _storage["selected_courses"].values()
                if (sc.custom_category or sc.course.category) == cat
            ]
        ))
    
    return requirements


# 学分设置相关
_credit_requirements: Dict[str, float] = {}


@router.post("/credits/settings", response_model=ApiResponse)
async def update_credit_requirements(
    requirements: Dict[str, float]
):
    """更新学分要求设置"""
    global _credit_requirements
    _credit_requirements = requirements
    
    from core.credit_manager import CreditManager
    credit_manager = CreditManager()
    
    for category, credits in requirements.items():
        credit_manager.set_required_credits(category, credits)
    
    return ApiResponse(success=True, message="学分要求已更新")


@router.get("/credits/settings", response_model=Dict[str, float])
async def get_credit_requirements():
    """获取当前学分要求设置"""
    global _credit_requirements
    
    if not _credit_requirements:
        from core.credit_manager import CreditManager
        credit_manager = CreditManager()
        _credit_requirements = {
            cat: req.required_credits 
            for cat, req in credit_manager.requirements.items()
        }
    
    return _credit_requirements
