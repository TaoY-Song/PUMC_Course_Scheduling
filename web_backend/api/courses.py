"""
课程管理API
提供课程加载、已选课程管理等功能
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..models.dto import (
    CourseDTO, SelectedCourseDTO, TimeSlotDTO,
    LoadCoursesResponse, ApiResponse
)
from ..dependencies import get_data_service
from core.services.interfaces import IDataService
from core.models import Course, SelectedCourse, TimeSlot

router = APIRouter(tags=["courses"])

_storage = {
    "courses": [],
    "selected_courses": {},
    "loaded_file_path": None
}

def _course_to_dto(course: Course, class_index: int = 0) -> CourseDTO:
    """将Course模型转换为DTO"""
    return CourseDTO(
        course_code=course.code,
        course_name=course.name,
        department=course.department,
        category=course.category,
        credits=course.credits,
        hours=course.hours,
        teacher=course.teacher,
        campus=course.campus,
        is_online=course.is_online,
        time_slots=[_timeslot_to_dto(ts) for ts in course.time_slots] if hasattr(course, 'time_slots') else [],
        class_index=class_index
    )

def _timeslot_to_dto(ts: TimeSlot) -> TimeSlotDTO:
    """将TimeSlot模型转换为DTO"""
    return TimeSlotDTO(
        day_of_week=ts.day_of_week,
        start_period=ts.start_period,
        end_period=ts.end_period,
        weeks=ts.weeks.copy()
    )

def _selected_course_to_dto(sc: SelectedCourse, selected_id: str = None) -> SelectedCourseDTO:
    """将SelectedCourse模型转换为DTO"""
    return SelectedCourseDTO(
        id=selected_id or str(id(sc)),
        course=_course_to_dto(sc.course, sc.class_num),
        class_index=sc.class_num,
        custom_category=sc.custom_category,
        is_category_locked=False,
        time_slots=[_timeslot_to_dto(ts) for ts in sc.time_slots]
    )

@router.post("/courses/load", response_model=LoadCoursesResponse)
async def load_courses(
    file: UploadFile = File(...),
    data_service: IDataService = Depends(get_data_service)
):
    """上传并加载课程Excel文件"""
    try:
        import tempfile
        import os
        
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            courses = data_service.load_courses(tmp_path)
            _storage["courses"] = courses
            _storage["loaded_file_path"] = tmp_path
            
            report = data_service.get_load_report()
            warnings = report.get("column_warnings", [])
            
            return LoadCoursesResponse(
                success=True,
                message=f"成功加载 {len(courses)} 门课程",
                course_count=len(courses),
                courses=[_course_to_dto(c, c.class_num) for c in courses],
                warnings=warnings
            )
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        return LoadCoursesResponse(
            success=False,
            message=f"加载失败: {str(e)}",
            course_count=0,
            courses=[],
            warnings=[]
        )

@router.get("/courses", response_model=List[CourseDTO])
async def get_courses():
    """获取已加载的所有课程"""
    return [_course_to_dto(c, c.class_num) for c in _storage["courses"]]

@router.get("/courses/search", response_model=List[CourseDTO])
async def search_courses(q: str):
    """搜索课程"""
    results = []
    query = q.lower()
    for course in _storage["courses"]:
        if (query in course.code.lower() or
            query in course.name.lower() or
            query in course.teacher.lower()):
            results.append(_course_to_dto(course, course.class_num))
    return results

# /selected-courses路由必须在 /courses/{course_code} 之前，否则会被误匹配
@router.get("/selected-courses", response_model=List[SelectedCourseDTO])
async def get_selected_courses():
    """获取所有已选课程"""
    return [_selected_course_to_dto(sc, selected_id) for selected_id, sc in _storage["selected_courses"].items()]

@router.post("/selected-courses", response_model=SelectedCourseDTO)
async def add_selected_course(
    course_code: str = Form(...),
    class_index: int = Form(default=0),
    data_service: IDataService = Depends(get_data_service)
):
    """添加课程到已选列表"""
    # 检查是否已存在相同课程
    for existing_id, existing in _storage["selected_courses"].items():
        if existing.course.code == course_code and existing.class_num == class_index:
            raise HTTPException(status_code=400, detail="课程已在已选列表中")
    
    course = None
    for c in _storage["courses"]:
        if c.code == course_code and c.class_num == class_index:
            course = c
            break
    
    if not course:
        raise HTTPException(status_code=404, detail="课程未找到")
    
    selected = SelectedCourse(course=course, class_num=class_index)
    selected_id = str(uuid.uuid4())
    _storage["selected_courses"][selected_id] = selected
    
    dto = _selected_course_to_dto(selected, selected_id)
    return dto

@router.delete("/selected-courses/{course_id}", response_model=ApiResponse)
async def remove_selected_course(course_id: str):
    """从已选列表移除课程"""
    if course_id not in _storage["selected_courses"]:
        raise HTTPException(status_code=404, detail="课程未找到")
    
    del _storage["selected_courses"][course_id]
    return ApiResponse(success=True, message="课程已移除")

@router.post("/selected-courses/{course_id}/timeslots", response_model=SelectedCourseDTO)
async def add_time_slot(
    course_id: str,
    time_slot: TimeSlotDTO
):
    """为已选课程添加时间段"""
    if course_id not in _storage["selected_courses"]:
        raise HTTPException(status_code=404, detail="课程未找到")
    
    selected = _storage["selected_courses"][course_id]
    ts = TimeSlot(
        day_of_week=time_slot.day_of_week,
        start_period=time_slot.start_period,
        end_period=time_slot.end_period,
        weeks=time_slot.weeks
    )
    selected.time_slots.append(ts)
    
    dto = _selected_course_to_dto(selected, course_id)
    return dto

@router.put("/selected-courses/{course_id}/category", response_model=SelectedCourseDTO)
async def update_course_category(
    course_id: str,
    category: str = Form(...)
):
    """更新已选课程的类别"""
    if course_id not in _storage["selected_courses"]:
        raise HTTPException(status_code=404, detail="课程未找到")
    
    selected = _storage["selected_courses"][course_id]
    selected.custom_category = category
    
    dto = _selected_course_to_dto(selected, course_id)
    return dto

@router.get("/courses/{course_code}", response_model=Optional[CourseDTO])
async def get_course(course_code: str):
    """获取指定课程的详细信息"""
    for course in _storage["courses"]:
        if course.code == course_code:
            return _course_to_dto(course)
    raise HTTPException(status_code=404, detail="课程未找到")
