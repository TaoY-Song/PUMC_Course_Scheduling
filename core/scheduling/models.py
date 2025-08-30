#!/usr/bin/env python3
"""
排课算法数据模型
定义排课结果、评分等数据结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import json

from ..models import Course, SelectedCourse


class ScheduleStatus(Enum):
    """排课状态"""

    SUCCESS = "success"  # 成功
    PARTIAL = "partial"  # 部分成功
    FAILED = "failed"  # 失败
    TIMEOUT = "timeout"  # 超时
    INFEASIBLE = "infeasible"  # 无可行解


@dataclass
class ConflictInfo:
    """冲突信息"""

    conflict_type: str  # 冲突类型：time, campus, credit
    course1: Course  # 冲突课程1
    course2: Optional[Course]  # 冲突课程2（可能为空）
    description: str  # 冲突描述
    severity: str  # 严重程度：high, medium, low


@dataclass
class ScheduleScore:
    """排课方案评分"""

    total_score: float = 0.0  # 总分（0-100）

    # 各项评分
    time_preference_score: float = 0.0  # 时间偏好分数
    campus_consistency_score: float = 0.0  # 校区一致性分数
    course_distribution_score: float = 0.0  # 课程分布分数
    credit_efficiency_score: float = 0.0  # 学分效率分数

    # 约束满足情况
    hard_constraints_satisfied: bool = True  # 硬约束是否满足
    soft_constraints_count: int = 0  # 满足的软约束数量
    total_soft_constraints: int = 0  # 总软约束数量

    # 统计信息
    total_courses: int = 0  # 总课程数
    total_credits: float = 0.0  # 总学分
    days_with_courses: int = 0  # 有课天数
    max_courses_per_day: int = 0  # 单天最多课程数
    campus_transfers: int = 0  # 跨校区次数

    def calculate_total_score(self) -> float:
        """计算总分（简化版本，不使用软约束）"""
        if not self.hard_constraints_satisfied:
            self.total_score = 0.0
            return self.total_score

        # 基于课程分布和学分效率的简单评分
        self.total_score = min(100.0, self.credit_efficiency_score)
        return self.total_score

    def get_grade(self) -> str:
        """获取评级"""
        if self.total_score >= 90:
            return "优秀"
        elif self.total_score >= 80:
            return "良好"
        elif self.total_score >= 70:
            return "中等"
        elif self.total_score >= 60:
            return "及格"
        else:
            return "不及格"


@dataclass
class ScheduleResult:
    """排课结果"""

    # 基本信息
    schedule_id: str  # 方案ID
    status: ScheduleStatus  # 排课状态
    selected_courses: List[SelectedCourse]  # 选中的课程

    # 评分信息
    score: ScheduleScore = field(default_factory=ScheduleScore)

    # 冲突和问题
    conflicts: List[ConflictInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # 统计信息
    solve_time_seconds: float = 0.0  # 求解时间
    total_courses_considered: int = 0  # 考虑的总课程数

    # 学分统计
    credit_summary: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if not self.selected_courses:
            self.selected_courses = []

        # 计算基本统计信息
        self._calculate_statistics()

    def _calculate_statistics(self):
        """计算统计信息"""
        if not self.selected_courses:
            return

        # 基本统计
        self.score.total_courses = len(self.selected_courses)
        self.score.total_credits = sum(
            course.course.credits for course in self.selected_courses
        )

        # 按天统计
        daily_courses = {}
        campuses_by_day = {}

        for selected_course in self.selected_courses:
            for time_slot in selected_course.time_slots:
                day = time_slot.weekday
                if day not in daily_courses:
                    daily_courses[day] = 0
                    campuses_by_day[day] = set()

                daily_courses[day] += 1
                campuses_by_day[day].add(selected_course.course.campus)

        self.score.days_with_courses = len(daily_courses)
        self.score.max_courses_per_day = (
            max(daily_courses.values()) if daily_courses else 0
        )

        # 计算跨校区次数
        self.score.campus_transfers = sum(
            len(campuses) - 1
            for campuses in campuses_by_day.values()
            if len(campuses) > 1
        )

    def add_conflict(
        self,
        conflict_type: str,
        course1: Course,
        course2: Optional[Course] = None,
        description: str = "",
        severity: str = "medium",
    ):
        """添加冲突信息"""
        conflict = ConflictInfo(
            conflict_type=conflict_type,
            course1=course1,
            course2=course2,
            description=description,
            severity=severity,
        )
        self.conflicts.append(conflict)

        # 如果有高严重程度冲突，标记硬约束不满足
        if severity == "high":
            self.score.hard_constraints_satisfied = False

    def add_warning(self, message: str):
        """添加警告信息"""
        self.warnings.append(message)

    def get_courses_by_day(self) -> Dict[int, List[SelectedCourse]]:
        """按天获取课程"""
        daily_courses = {}

        for selected_course in self.selected_courses:
            for time_slot in selected_course.time_slots:
                day = time_slot.weekday
                if day not in daily_courses:
                    daily_courses[day] = []
                daily_courses[day].append(selected_course)

        return daily_courses

    def get_time_conflicts(self) -> List[ConflictInfo]:
        """获取时间冲突"""
        return [c for c in self.conflicts if c.conflict_type == "time"]

    def get_campus_conflicts(self) -> List[ConflictInfo]:
        """获取校区冲突"""
        return [c for c in self.conflicts if c.conflict_type == "campus"]

    def has_conflicts(self) -> bool:
        """是否有冲突"""
        return len(self.conflicts) > 0

    def is_feasible(self) -> bool:
        """是否可行"""
        return (
            self.status in [ScheduleStatus.SUCCESS, ScheduleStatus.PARTIAL]
            and self.score.hard_constraints_satisfied
        )

    def get_summary(self) -> str:
        """获取方案摘要"""
        status_text = {
            ScheduleStatus.SUCCESS: "成功",
            ScheduleStatus.PARTIAL: "部分成功",
            ScheduleStatus.FAILED: "失败",
            ScheduleStatus.TIMEOUT: "超时",
            ScheduleStatus.INFEASIBLE: "无可行解",
        }

        summary = f"""排课方案 {self.schedule_id}
状态: {status_text.get(self.status, "未知")}
总分: {self.score.total_score:.1f} ({self.score.get_grade()})
课程数: {self.score.total_courses} 门
总学分: {self.score.total_credits:.1f}
有课天数: {self.score.days_with_courses} 天
冲突数: {len(self.conflicts)} 个
求解时间: {self.solve_time_seconds:.2f} 秒"""

        return summary

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "schedule_id": self.schedule_id,
            "status": self.status.value,
            "score": {
                "total_score": self.score.total_score,
                "time_preference_score": self.score.time_preference_score,
                "campus_consistency_score": self.score.campus_consistency_score,
                "course_distribution_score": self.score.course_distribution_score,
                "credit_efficiency_score": self.score.credit_efficiency_score,
                "hard_constraints_satisfied": self.score.hard_constraints_satisfied,
                "grade": self.score.get_grade(),
            },
            "statistics": {
                "total_courses": self.score.total_courses,
                "total_credits": self.score.total_credits,
                "days_with_courses": self.score.days_with_courses,
                "max_courses_per_day": self.score.max_courses_per_day,
                "campus_transfers": self.score.campus_transfers,
            },
            "conflicts_count": len(self.conflicts),
            "warnings_count": len(self.warnings),
            "solve_time_seconds": self.solve_time_seconds,
            "is_feasible": self.is_feasible(),
        }

    def export_to_json(self, file_path: str):
        """导出为JSON文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
