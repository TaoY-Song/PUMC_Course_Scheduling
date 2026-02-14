"""
数据传输对象(DTO)定义
用于API请求和响应的数据验证与序列化
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ==================== 枚举类型 ====================

class CreditConstraintMode(str, Enum):
    """学分约束模式"""
    REQUIRED = "REQUIRED"
    OPTIMAL = "OPTIMAL"


class CampusConflictMode(str, Enum):
    """校区冲突模式"""
    DAILY = "DAILY"
    PERIOD = "PERIOD"
    DISABLED = "DISABLED"


class SchedulingStatus(str, Enum):
    """排课状态"""
    IDLE = "idle"
    CONFIGURING = "configuring"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==================== 基础模型 ====================

class TimeSlotDTO(BaseModel):
    """时间段DTO"""
    day_of_week: int = Field(..., ge=1, le=7, description="星期几(1-7)")
    start_period: int = Field(..., ge=1, le=12, description="开始节次")
    end_period: int = Field(..., ge=1, le=12, description="结束节次")
    weeks: List[int] = Field(default_factory=list, description="上课周次列表")


class CourseDTO(BaseModel):
    """课程DTO"""
    course_code: str = Field(..., description="课程编码")
    course_name: str = Field(..., description="课程名称")
    department: str = Field(..., description="开课院系")
    category: str = Field(..., description="课程类别")
    credits: float = Field(..., description="学分")
    hours: int = Field(..., description="学时")
    teacher: Optional[str] = Field(None, description="任课教师")
    campus: Optional[str] = Field(None, description="校区")
    is_online: bool = Field(False, description="是否线上课程")
    time_slots: List[TimeSlotDTO] = Field(default_factory=list, description="时间段列表")
    class_index: int = Field(0, description="班次索引")
    
    class Config:
        from_attributes = True


class SelectedCourseDTO(BaseModel):
    """已选课程DTO"""
    id: str = Field(..., description="唯一标识")
    course: CourseDTO = Field(..., description="课程信息")
    class_index: int = Field(..., description="班次索引")
    custom_category: Optional[str] = Field(None, description="自定义类别")
    is_category_locked: bool = Field(False, description="类别是否锁定")
    time_slots: List[TimeSlotDTO] = Field(default_factory=list, description="自定义时间段")
    
    class Config:
        from_attributes = True


# ==================== 配置模型 ====================

class SchedulingConfigDTO(BaseModel):
    """排课配置DTO"""
    credit_constraint_mode: CreditConstraintMode = Field(
        default=CreditConstraintMode.OPTIMAL,
        description="学分约束模式"
    )
    campus_conflict_mode: CampusConflictMode = Field(
        default=CampusConflictMode.DAILY,
        description="校区冲突模式"
    )
    max_solutions: int = Field(default=1, ge=1, le=10, description="最大解数量")
    time_limit: int = Field(default=60, ge=10, le=300, description="时间限制(秒)")
    credit_overflow_ratio: float = Field(default=0.1, ge=0.0, le=0.5, description="学分溢出比例")
    campus_transition_time: int = Field(default=30, ge=0, le=120, description="校区转换时间(分钟)")


# ==================== 学分模型 ====================

class CreditRequirementDTO(BaseModel):
    """学分要求DTO"""
    category: str = Field(..., description="学分类别")
    required_credits: float = Field(..., description="要求学分")
    completed_credits: float = Field(default=0.0, description="已完成学分")
    remaining_credits: float = Field(default=0.0, description="剩余学分")
    is_completed: bool = Field(default=False, description="是否已完成")
    courses: List[SelectedCourseDTO] = Field(default_factory=list, description="该类别的课程列表")


class CreditSettingsDTO(BaseModel):
    """学分设置DTO"""
    requirements: Dict[str, float] = Field(
        default_factory=dict,
        description="类别到学分的映射"
    )


# ==================== 排课结果模型 ====================

class ScheduleScoreDTO(BaseModel):
    """排课评分DTO"""
    total_score: float = Field(..., description="总分")
    credit_match_score: float = Field(..., description="学分匹配度得分")
    time_quality_score: float = Field(..., description="时间质量得分")


class ConflictInfoDTO(BaseModel):
    """冲突信息DTO"""
    course1_code: str = Field(..., description="课程1编码")
    course2_code: str = Field(..., description="课程2编码")
    conflict_type: str = Field(..., description="冲突类型")
    description: str = Field(..., description="冲突描述")


class ScheduleResultDTO(BaseModel):
    """排课结果DTO"""
    id: str = Field(..., description="结果ID")
    selected_courses: List[SelectedCourseDTO] = Field(..., description="选中的课程")
    score: ScheduleScoreDTO = Field(..., description="评分")
    conflicts: List[ConflictInfoDTO] = Field(default_factory=list, description="冲突列表")
    execution_time: float = Field(..., description="执行时间(秒)")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        from_attributes = True


# ==================== 请求/响应模型 ====================

class LoadCoursesRequest(BaseModel):
    """加载课程请求"""
    file_path: str = Field(..., description="Excel文件路径")


class LoadCoursesResponse(BaseModel):
    """加载课程响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    course_count: int = Field(0, description="课程数量")
    courses: List[CourseDTO] = Field(default_factory=list, description="课程列表")
    warnings: List[str] = Field(default_factory=list, description="加载警告列表")


class AddSelectedCourseRequest(BaseModel):
    """添加已选课程请求"""
    course_code: str = Field(..., description="课程编码")
    class_index: int = Field(0, description="班次索引")


class ConfigureSchedulingRequest(BaseModel):
    """配置排课请求"""
    config: SchedulingConfigDTO = Field(..., description="配置信息")


class ExecuteSchedulingRequest(BaseModel):
    """执行排课请求"""
    course_ids: List[str] = Field(default_factory=list, description="要排课的课程ID列表")


class ExecuteSchedulingResponse(BaseModel):
    """执行排课响应"""
    success: bool = Field(..., description="是否成功")
    result: Optional[ScheduleResultDTO] = Field(None, description="排课结果")
    error_message: Optional[str] = Field(None, description="错误信息")


class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field(default="xlsx", description="导出格式")
    file_path: str = Field(..., description="导出文件路径")


class ExportResponse(BaseModel):
    """导出响应"""
    success: bool = Field(..., description="是否成功")
    file_path: Optional[str] = Field(None, description="导出的文件路径")
    message: str = Field(..., description="消息")


class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    data: Optional[Any] = Field(None, description="数据")
