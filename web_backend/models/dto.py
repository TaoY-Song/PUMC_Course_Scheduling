"""Pydantic DTO definitions for the web backend."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CreditConstraintMode(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIMAL = "OPTIMAL"


class CampusConflictMode(str, Enum):
    DAILY = "DAILY"
    PERIOD = "PERIOD"
    DISABLED = "DISABLED"


class SchedulingStatus(str, Enum):
    IDLE = "idle"
    CONFIGURING = "configuring"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TimeSlotDTO(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7)
    start_period: int = Field(..., ge=1, le=10)
    end_period: int = Field(..., ge=1, le=10)
    weeks: List[int] = Field(default_factory=list)


class CourseDTO(BaseModel):
    course_code: str
    course_name: str
    department: str
    category: str
    credits: float
    hours: int
    teacher: Optional[str] = None
    campus: Optional[str] = None
    is_online: bool = False
    time_slots: List[TimeSlotDTO] = Field(default_factory=list)
    class_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class SelectedCourseDTO(BaseModel):
    id: str
    course: CourseDTO
    class_index: int
    custom_category: Optional[str] = None
    is_category_locked: bool = False
    is_online: bool = False
    time_slots: List[TimeSlotDTO] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SelectedCourseUpdateDTO(BaseModel):
    custom_category: Optional[str] = None
    is_online: Optional[bool] = None
    is_category_locked: Optional[bool] = None


class SchedulingConfigDTO(BaseModel):
    credit_constraint_mode: CreditConstraintMode = CreditConstraintMode.OPTIMAL
    campus_conflict_mode: CampusConflictMode = CampusConflictMode.DAILY
    max_solutions: int = Field(default=1, ge=1, le=10)
    time_limit: int = Field(default=60, ge=10, le=300)
    # 学分溢出上限用固定学分（不是比例）。比例制在小缺口上张不开：
    # 限选要求 1.0 分、ratio=0.2 时上限只 1.2，连 1.5 分的课都收不下，
    # 而培养方案写的是「>=1 学分」，只有下限。
    credit_overflow: float = Field(default=1.0, ge=0.0, le=10.0)
    # 已删除 campus_transition_time：PERIOD 模式现在按半天时段分块
    # 判定（上午/下午/晚上），没有“隔几节”这个可调阈值。
    # 留个不生效的旋钮比删掉它更坑人。


class CreditRequirementDTO(BaseModel):
    category: str
    required_credits: float
    completed_credits: float = 0.0
    remaining_credits: float = 0.0
    is_completed: bool = False
    courses: List[SelectedCourseDTO] = Field(default_factory=list)


class CreditSettingsDTO(BaseModel):
    requirements: Dict[str, float] = Field(default_factory=dict)


class ScheduleScoreDTO(BaseModel):
    total_score: float
    credit_match_score: float
    time_quality_score: float


class ConflictInfoDTO(BaseModel):
    course1_code: str
    course2_code: str
    conflict_type: str
    description: str


class ScheduleResultDTO(BaseModel):
    id: str
    selected_courses: List[SelectedCourseDTO]
    score: ScheduleScoreDTO
    conflicts: List[ConflictInfoDTO] = Field(default_factory=list)
    execution_time: float
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class LoadCoursesRequest(BaseModel):
    file_path: str


class LoadCoursesResponse(BaseModel):
    success: bool
    message: str
    course_count: int = 0
    courses: List[CourseDTO] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AddSelectedCourseRequest(BaseModel):
    course_code: str
    class_index: int = 0


class ConfigureSchedulingRequest(BaseModel):
    config: SchedulingConfigDTO


class ExecuteSchedulingRequest(BaseModel):
    course_ids: List[str] = Field(default_factory=list)


class TaskResponseBase(BaseModel):
    success: bool = True
    task_id: str
    status: TaskStatus
    message: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    is_active: bool = False
    is_finished: bool = False
    can_cancel: bool = False
    # 🔧 P1 修复：补上进度字段。前端一直在读 percent，但 DTO 从未返回。
    percent: int = 0


class ExecuteSchedulingResponse(TaskResponseBase):
    result: Optional[ScheduleResultDTO] = None


class SchedulingTaskStatusResponse(TaskResponseBase):
    has_result: bool = False
    result: Optional[ScheduleResultDTO] = None


class SchedulingTaskResultResponse(TaskResponseBase):
    has_result: bool = False
    result: Optional[ScheduleResultDTO] = None


class ExportRequest(BaseModel):
    format: str = "xlsx"
    file_path: str


class ExportResponse(BaseModel):
    success: bool
    file_path: Optional[str] = None
    message: str


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
