"""Supplement test API for the web workbench."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.services.course_supplement_service import CourseSupplementService

from ..dependencies import get_web_session
from ..models.dto import ApiResponse
from ..state import WebSessionContext
from ..uploads import read_upload_bytes

router = APIRouter(tags=["supplement"])


def _timestamp_token() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


@router.post("/supplement/run", response_model=ApiResponse)
async def run_supplement_test(
    schedule_result_file: UploadFile = File(...),
    course_list_file: UploadFile | None = File(default=None),
    session: WebSessionContext = Depends(get_web_session),
):
    """Run the supplement script against an exported schedule result file."""
    session.artifacts_dir.mkdir(parents=True, exist_ok=True)
    token = _timestamp_token()

    schedule_suffix = Path(
        schedule_result_file.filename or "schedule_result.xlsx"
    ).suffix.lower() or ".xlsx"
    if schedule_suffix not in {".xls", ".xlsx"}:
        raise HTTPException(status_code=400, detail="排课结果必须是 Excel 文件")
    schedule_path = session.artifacts_dir / f"supplement_schedule_input_{token}{schedule_suffix}"
    schedule_path.write_bytes(await read_upload_bytes(schedule_result_file))

    if course_list_file is not None:
        course_suffix = Path(
            course_list_file.filename or "course_catalog.xlsx"
        ).suffix.lower() or ".xlsx"
        if course_suffix not in {".xls", ".xlsx"}:
            schedule_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="备选课程表必须是 Excel 文件")
        course_path = session.artifacts_dir / f"supplement_course_catalog_{token}{course_suffix}"
        try:
            course_path.write_bytes(await read_upload_bytes(course_list_file))
        except Exception:
            schedule_path.unlink(missing_ok=True)
            raise
        course_source = "uploaded"
    else:
        if not session.loaded_course_file:
            raise HTTPException(status_code=400, detail="请先导入课程一览表，或在本页上传备选课程表")

        course_path = Path(session.loaded_course_file)
        if not course_path.exists():
            raise HTTPException(status_code=400, detail="当前会话中的课程一览表已失效，请重新导入")
        course_source = "session"

    log_path = session.artifacts_dir / f"supplement_{token}.log"
    output_name = f"supplement_result_{token}.xlsx"
    service = CourseSupplementService(
        log_file_path=str(log_path),
        output_file_name=output_name,
    )

    result = service.run_supplement_test(str(schedule_path), str(course_path))
    success = bool(result.get("success"))
    output_file = Path(result.get("output_file", "")) if result.get("output_file") else None

    data = {
        "added_courses": result.get("added_courses", []),
        "failed_courses": result.get("failed_courses", []),
        "stats": result.get("stats", {}),
        "output_file_name": output_file.name if output_file and output_file.exists() else None,
        "log_file_name": log_path.name if log_path.exists() else None,
        "schedule_result_source": schedule_path.name,
        "course_list_source": course_path.name,
        "course_list_source_type": course_source,
    }

    return ApiResponse(
        success=success,
        message="补充测试完成" if success else result.get("error", "补充测试失败"),
        data=data,
    )
