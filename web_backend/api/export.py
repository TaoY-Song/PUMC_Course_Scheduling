"""Import/export APIs for the web workbench."""

from __future__ import annotations

import mimetypes
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.models import SelectedCourse
from core.services.interfaces import IDataService

from ..api.courses import _selected_course_to_dto
from ..dependencies import get_data_service, get_web_session
from ..models.dto import ApiResponse
from ..state import WebSessionContext

router = APIRouter(tags=["export"])


def _artifact_name(prefix: str, suffix: str = ".xlsx") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    token = uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{token}{suffix}"


def _artifact_path(session: WebSessionContext, prefix: str, suffix: str = ".xlsx") -> Path:
    session.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return session.artifacts_dir / _artifact_name(prefix, suffix)


def _weekday_label(value: int) -> str:
    mapping = {
        1: "周一",
        2: "周二",
        3: "周三",
        4: "周四",
        5: "周五",
        6: "周六",
        7: "周日",
    }
    return mapping.get(value, f"周{value}")


def _format_weeks(weeks: list[int]) -> str:
    if not weeks:
        return ""

    normalized = sorted(set(int(week) for week in weeks))
    ranges: list[str] = []
    start = normalized[0]
    end = start

    for week in normalized[1:]:
        if week == end + 1:
            end = week
            continue

        ranges.append(str(start) if start == end else f"{start}-{end}")
        start = week
        end = week

    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ",".join(ranges)


def _format_time_slots(course: SelectedCourse) -> str:
    if course.is_online:
        return "线上课程"

    if not course.time_slots:
        return "未设置时间"

    fragments: list[str] = []
    for slot in course.time_slots:
        weeks = _format_weeks(list(slot.weeks))
        week_text = f"（第{weeks}周）" if weeks else ""
        fragments.append(
            f"{_weekday_label(slot.weekday)} 第{slot.start_section}-{slot.end_section}节{week_text}"
        )

    return "；".join(fragments)


def _build_time_columns(course: SelectedCourse, max_time_slots: int = 5) -> list[str | int]:
    columns: list[str | int] = []

    for index in range(max_time_slots):
        if index < len(course.time_slots):
            slot = course.time_slots[index]
            columns.extend(
                [
                    slot.weekday,
                    f"{slot.start_section}-{slot.end_section}",
                    _format_weeks(list(slot.weeks)),
                ]
            )
        else:
            columns.extend(["", "", ""])

    return columns


def _autosize_worksheet(worksheet) -> None:
    for column_cells in worksheet.columns:
        length = 0
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            length = max(length, len(value))
        worksheet.column_dimensions[column_letter].width = min(max(length + 2, 10), 36)


def _build_flat_schedule_export(courses: list[SelectedCourse], destination: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "课程列表"

    headers = [
        "课程编码",
        "课程名称",
        "开课院系",
        "课程类别",
        "班次",
        "校区",
        "任课教师",
        "学分",
        "学时",
        "自定义类别",
        "是否线上",
    ]
    for index in range(1, 6):
        headers.extend([f"星期几{index}", f"节次{index}", f"周次{index}"])
    worksheet.append(headers)

    for course in courses:
        worksheet.append(
            [
                course.course.code,
                course.course.name,
                course.course.department,
                course.course.category,
                course.class_num,
                course.course.campus or "",
                course.course.teacher or "",
                course.course.credits,
                course.course.hours,
                course.custom_category or "",
                "是" if course.is_online else "否",
                *_build_time_columns(course),
            ]
        )

    _autosize_worksheet(worksheet)
    workbook.save(destination)


def _media_type_for_path(path: Path) -> str:
    if path.suffix.lower() == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


@router.get("/export/selected-courses")
async def export_selected_courses(
    data_service: IDataService = Depends(get_data_service),
    session: WebSessionContext = Depends(get_web_session),
):
    """Export current selected courses as an Excel workbook download."""
    selected_courses = session.list_selected_courses()
    if not selected_courses:
        raise HTTPException(status_code=400, detail="当前没有可导出的已选课程")

    export_path = _artifact_path(session, "selected_courses")
    success = data_service.export_selected_courses(selected_courses, str(export_path))
    if not success:
        raise HTTPException(status_code=500, detail="已选课程导出失败")

    return FileResponse(
        str(export_path),
        filename=export_path.name,
        media_type=_media_type_for_path(export_path),
    )


@router.get("/export/schedule-result")
async def export_schedule_result(session: WebSessionContext = Depends(get_web_session)):
    """Export the latest schedule result as a flat Excel file."""
    if session.last_scheduling_result is None:
        raise HTTPException(status_code=400, detail="当前没有可导出的排课结果")

    export_path = _artifact_path(session, "schedule_result_flat")
    _build_flat_schedule_export(session.last_scheduling_result.selected_courses, export_path)

    return FileResponse(
        str(export_path),
        filename=export_path.name,
        media_type=_media_type_for_path(export_path),
    )


@router.post("/import/selected-courses", response_model=ApiResponse)
async def import_selected_courses(
    file: UploadFile = File(...),
    data_service: IDataService = Depends(get_data_service),
    session: WebSessionContext = Depends(get_web_session),
):
    """Import selected courses from Excel."""
    try:
        suffix = Path(file.filename or "selected_courses.xlsx").suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            courses = data_service.import_selected_courses(
                tmp_path,
                session.loaded_courses,
            )

            session.clear_selected_courses()
            response_courses = []
            for course in courses:
                if not hasattr(course, "is_category_locked"):
                    course.is_category_locked = False
                selected_id = str(uuid4())
                session.selected_courses[selected_id] = course
                response_courses.append(_selected_course_to_dto(course, selected_id))

            return ApiResponse(
                success=True,
                message=f"成功导入 {len(courses)} 门课程",
                data={"courses": response_courses},
            )
        finally:
            os.unlink(tmp_path)

    except Exception as error:
        return ApiResponse(success=False, message=str(error))


@router.get("/export/download/{file_name}")
async def download_file(
    file_name: str,
    session: WebSessionContext = Depends(get_web_session),
):
    """Download a previously generated artifact."""
    file_path = session.artifacts_dir / file_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件未找到")

    return FileResponse(
        str(file_path),
        filename=file_path.name,
        media_type=_media_type_for_path(file_path),
    )
