"""Course management APIs for the web workbench."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.models import Course, SelectedCourse, TimeSlot
from core.services.interfaces import IDataService

from ..dependencies import get_data_service, get_web_session
from ..models.dto import (
    ApiResponse,
    CourseDTO,
    LoadCoursesResponse,
    SelectedCourseDTO,
    SelectedCourseUpdateDTO,
    TimeSlotDTO,
)
from ..state import WebSessionContext

router = APIRouter(tags=["courses"])


def _timeslot_to_dto(time_slot: TimeSlot) -> TimeSlotDTO:
    return TimeSlotDTO(
        day_of_week=time_slot.weekday,
        start_period=time_slot.start_section,
        end_period=time_slot.end_section,
        weeks=list(time_slot.weeks),
    )


def _timeslot_from_dto(time_slot: TimeSlotDTO) -> TimeSlot:
    return TimeSlot(
        weekday=time_slot.day_of_week,
        start_section=time_slot.start_period,
        end_section=time_slot.end_period,
        weeks=list(time_slot.weeks),
    )


def _course_to_dto(course: Course, class_index: int = 0) -> CourseDTO:
    return CourseDTO(
        course_code=course.code,
        course_name=course.name,
        department=course.department,
        category=course.category,
        credits=course.credits,
        hours=int(course.hours),
        teacher=course.teacher,
        campus=course.campus,
        is_online=course.is_online,
        time_slots=[_timeslot_to_dto(time_slot) for time_slot in getattr(course, "time_slots", []) or []],
        class_index=class_index,
    )


def _selected_course_to_dto(
    selected_course: SelectedCourse,
    selected_id: Optional[str] = None,
) -> SelectedCourseDTO:
    return SelectedCourseDTO(
        id=selected_id or str(uuid4()),
        course=_course_to_dto(selected_course.course, selected_course.class_num),
        class_index=selected_course.class_num,
        custom_category=selected_course.custom_category,
        is_category_locked=getattr(selected_course, "is_category_locked", False),
        is_online=selected_course.is_online,
        time_slots=[_timeslot_to_dto(time_slot) for time_slot in selected_course.time_slots],
    )


def _find_loaded_course(session: WebSessionContext, course_code: str, class_index: int) -> Course:
    matches = session.find_courses(course_code, class_index)
    if not matches:
        raise HTTPException(status_code=404, detail="课程未找到")
    return matches[0]


def _resolve_selected_course(session: WebSessionContext, course_id: str) -> SelectedCourse:
    selected_course = session.get_selected_course(course_id)
    if not selected_course:
        raise HTTPException(status_code=404, detail="课程未找到")
    return selected_course


@router.post("/courses/load", response_model=LoadCoursesResponse)
async def load_courses(
    file: UploadFile = File(...),
    data_service: IDataService = Depends(get_data_service),
    session: WebSessionContext = Depends(get_web_session),
):
    suffix = Path(file.filename or "courses.xlsx").suffix or ".xlsx"

    try:
        for candidate in session.artifacts_dir.glob("current_course_catalog.*"):
            try:
                candidate.unlink()
            except OSError:
                continue

        saved_path = session.artifacts_dir / f"current_course_catalog{suffix}"
        saved_path.write_bytes(await file.read())

        courses = data_service.load_courses(str(saved_path))
        session.set_loaded_courses(courses, str(saved_path))
        report = data_service.get_load_report()
        warnings = report.get("column_warnings", [])

        return LoadCoursesResponse(
            success=True,
            message=f"成功加载 {len(courses)} 门课程",
            course_count=len(courses),
            courses=[_course_to_dto(course, course.class_num) for course in courses],
            warnings=warnings,
        )
    except Exception as error:  # pragma: no cover
        return LoadCoursesResponse(
            success=False,
            message=f"加载失败: {error}",
            course_count=0,
            courses=[],
            warnings=[],
        )


@router.get("/courses", response_model=List[CourseDTO])
async def get_courses(session: WebSessionContext = Depends(get_web_session)):
    return [_course_to_dto(course, course.class_num) for course in session.loaded_courses]


@router.get("/courses/search", response_model=List[CourseDTO])
async def search_courses(q: str, session: WebSessionContext = Depends(get_web_session)):
    query = q.strip().lower()
    results: List[CourseDTO] = []

    for course in session.loaded_courses:
        teacher = course.teacher or ""
        if query in course.code.lower() or query in course.name.lower() or query in teacher.lower():
            results.append(_course_to_dto(course, course.class_num))

    return results


@router.get("/selected-courses", response_model=List[SelectedCourseDTO])
async def get_selected_courses(session: WebSessionContext = Depends(get_web_session)):
    return [
        _selected_course_to_dto(selected_course, selected_id)
        for selected_id, selected_course in session.selected_courses.items()
    ]


@router.post("/selected-courses", response_model=SelectedCourseDTO)
async def add_selected_course(
    course_code: str = Form(...),
    class_index: int = Form(default=0),
    session: WebSessionContext = Depends(get_web_session),
):
    normalized_code = course_code.strip().upper()

    for existing in session.selected_courses.values():
        if existing.course.code.upper() == normalized_code and existing.class_num == class_index:
            raise HTTPException(status_code=400, detail="课程已在已选列表中")

    course = _find_loaded_course(session, normalized_code, class_index)
    selected_id, selected_course = session.add_selected_course(
        course=course,
        class_index=class_index,
        is_online=course.is_online,
        custom_category=course.custom_category or "",
        is_category_locked=False,
    )
    return _selected_course_to_dto(selected_course, selected_id)


@router.delete("/selected-courses", response_model=ApiResponse)
async def clear_selected_courses(session: WebSessionContext = Depends(get_web_session)):
    session.clear_selected_courses()
    return ApiResponse(success=True, message="已清空所有已选课程")


@router.delete("/selected-courses/{course_id}", response_model=ApiResponse)
async def remove_selected_course(
    course_id: str,
    session: WebSessionContext = Depends(get_web_session),
):
    if not session.remove_selected_course(course_id):
        raise HTTPException(status_code=404, detail="课程未找到")
    return ApiResponse(success=True, message="课程已移除")


@router.post("/selected-courses/{course_id}/timeslots", response_model=SelectedCourseDTO)
async def add_time_slot(
    course_id: str,
    time_slot: TimeSlotDTO,
    session: WebSessionContext = Depends(get_web_session),
):
    selected_course = session.add_time_slot(course_id, _timeslot_from_dto(time_slot))
    if not selected_course:
        raise HTTPException(status_code=404, detail="课程未找到")
    return _selected_course_to_dto(selected_course, course_id)


@router.put("/selected-courses/{course_id}/timeslots/{time_slot_index}", response_model=SelectedCourseDTO)
async def update_time_slot(
    course_id: str,
    time_slot_index: int,
    time_slot: TimeSlotDTO,
    session: WebSessionContext = Depends(get_web_session),
):
    selected_course = session.update_time_slot(course_id, time_slot_index, _timeslot_from_dto(time_slot))
    if not selected_course:
        raise HTTPException(status_code=404, detail="时间段未找到")
    return _selected_course_to_dto(selected_course, course_id)


@router.delete("/selected-courses/{course_id}/timeslots/{time_slot_index}", response_model=SelectedCourseDTO)
async def delete_time_slot(
    course_id: str,
    time_slot_index: int,
    session: WebSessionContext = Depends(get_web_session),
):
    selected_course = session.delete_time_slot(course_id, time_slot_index)
    if not selected_course:
        raise HTTPException(status_code=404, detail="时间段未找到")
    return _selected_course_to_dto(selected_course, course_id)


@router.patch("/selected-courses/{course_id}", response_model=SelectedCourseDTO)
async def update_selected_course(
    course_id: str,
    payload: SelectedCourseUpdateDTO = Body(...),
    session: WebSessionContext = Depends(get_web_session),
):
    selected_course = _resolve_selected_course(session, course_id)

    if payload.custom_category is not None:
        category = payload.custom_category.strip()
        if not category:
            raise HTTPException(status_code=400, detail="课程类别不能为空")
        selected_course.custom_category = category

    if payload.is_online is not None:
        selected_course.is_online = payload.is_online

    if payload.is_category_locked is not None:
        selected_course.is_category_locked = payload.is_category_locked

    session.invalidate_scheduling_result()
    return _selected_course_to_dto(selected_course, course_id)


@router.put("/selected-courses/{course_id}/category", response_model=SelectedCourseDTO)
async def update_course_category(
    course_id: str,
    category: str = Form(...),
    session: WebSessionContext = Depends(get_web_session),
):
    return await update_selected_course(
        course_id,
        SelectedCourseUpdateDTO(custom_category=category),
        session,
    )


@router.get("/courses/{course_code}", response_model=Optional[CourseDTO])
async def get_course(course_code: str, session: WebSessionContext = Depends(get_web_session)):
    matches = session.find_courses(course_code.strip().upper())
    if not matches:
        raise HTTPException(status_code=404, detail="课程未找到")
    return _course_to_dto(matches[0], matches[0].class_num)
