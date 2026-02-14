"""
导入导出API
提供课程和排课结果的导入导出功能
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..models.dto import ApiResponse
from ..dependencies import get_data_service
from ..api.courses import _storage, _selected_course_to_dto
from core.services.interfaces import IDataService

router = APIRouter(tags=["export"])

@router.post("/export/selected-courses", response_model=ApiResponse)
async def export_selected_courses(
    file_path: str = Form(...),
    data_service: IDataService = Depends(get_data_service)
):
    """导出已选课程到Excel"""
    try:
        selected_courses = list(_storage["selected_courses"].values())
        success = data_service.export_selected_courses(selected_courses, file_path)
        
        return ApiResponse(
            success=success,
            message="导出成功" if success else "导出失败",
            data={"file_path": file_path}
        )
    except Exception as e:
        return ApiResponse(success=False, message=str(e))

@router.post("/export/schedule-result", response_model=ApiResponse)
async def export_schedule_result(
    file_path: str = Form(...),
    data_service: IDataService = Depends(get_data_service)
):
    """导出排课结果到Excel"""
    try:
        from ..api.scheduling import _last_result
        
        if _last_result is None:
            return ApiResponse(success=False, message="没有可导出的排课结果")
        
        from core.scheduling.models import ScheduleResult, ScheduleScore
        
        result = ScheduleResult(
            selected_courses=_last_result["courses"],
            score=_last_result["score"],
            conflicts=_last_result["conflicts"],
            execution_time=_last_result["execution_time"]
        )
        
        success = data_service.export_scheduling_result(result, file_path)
        
        return ApiResponse(
            success=success,
            message="导出成功" if success else "导出失败",
            data={"file_path": file_path}
        )
    except Exception as e:
        return ApiResponse(success=False, message=str(e))

@router.post("/import/selected-courses", response_model=ApiResponse)
async def import_selected_courses(
    file: UploadFile = File(...),
    data_service: IDataService = Depends(get_data_service)
):
    """从Excel导入已选课程"""
    try:
        import tempfile
        import os
        
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            courses = data_service.import_selected_courses(
                tmp_path, 
                _storage["courses"]
            )
            
            for course in courses:
                course_id = str(len(_storage["selected_courses"]))
                _storage["selected_courses"][course_id] = course
            
            return ApiResponse(
                success=True,
                message=f"成功导入 {len(courses)} 门课程",
                data={
                    "courses": [_selected_course_to_dto(c) for c in courses]
                }
            )
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        return ApiResponse(success=False, message=str(e))

@router.get("/export/download/{file_name}")
async def download_file(file_name: str):
    """下载导出文件"""
    file_path = Path("./exports") / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件未找到")
    
    return FileResponse(
        str(file_path),
        filename=file_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
