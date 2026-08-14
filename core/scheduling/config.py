#!/usr/bin/env python3
"""
排课算法配置管理
定义排课过程中的各种配置选项和约束参数
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List


class CampusConflictMode(Enum):
    """校区冲突处理模式"""

    DAILY = "daily"  # 日内模式：同一天不允许跨校区
    PERIOD = "period"  # 时段模式：相邻时段不允许跨校区，需要足够的转换时间
    DISABLED = "disabled"  # 禁用模式：不检查校区冲突


# OnlineCourseMode 已删除 - 线上课程统一使用高优先级处理逻辑


class CreditConstraintMode(Enum):
    """学分约束处理模式"""

    REQUIRED = "required"  # 必需模式：学分下限是硬约束，必须满足
    OPTIMAL = "optimal"  # 优化模式：学分下限是软约束，尽力满足


@dataclass
class SchedulingConfig:
    """排课算法配置类"""

    # 校区冲突配置
    campus_conflict_mode: CampusConflictMode = CampusConflictMode.DAILY
    min_campus_transfer_time: int = 2  # 跨校区最小间隔时间（节次）

    # 学分约束配置
    credit_constraint_mode: CreditConstraintMode = (
        CreditConstraintMode.OPTIMAL
    )  # 学分约束模式（与UI默认保持一致）
    allow_credit_overflow: bool = True  # 是否允许学分超出要求
    max_credit_overflow_ratio: float = 0.2  # 最大学分超出比例
    credit_gap_weight: float = (
        0.1  # 学分缺口权重（灵活模式下使用，设置为较小值避免过度惩罚）
    )

    # 时间偏好配置
    avoid_early_morning: bool = False  # 是否避免早课（1-2节）
    avoid_late_evening: bool = False  # 是否避免晚课（9-10节）
    lunch_break_protection: bool = False  # 是否保护午休时间（5-6节）

    # 求解器配置
    max_solve_time_seconds: int = 30  # 最大求解时间
    max_solutions: int = 100  # 最大解数量

    def validate(self) -> List[str]:
        """验证配置的有效性"""
        errors = []

        # 验证时间间隔
        if self.min_campus_transfer_time < 0:
            errors.append("跨校区最小间隔时间不能为负数")

        # 验证学分超出比例
        if self.max_credit_overflow_ratio < 0 or self.max_credit_overflow_ratio > 1:
            errors.append("最大学分超出比例应在0-1之间")

        # 验证学分缺口权重
        if self.credit_gap_weight < 0:
            errors.append("学分缺口权重不能为负数")

        # 验证求解器配置
        if self.max_solve_time_seconds <= 0:
            errors.append("最大求解时间应大于0")

        if self.max_solutions <= 0:
            errors.append("最大解数量应大于0")

        return errors

    def get_time_preference_score(self, start_section: int) -> float:
        """获取时间段偏好分数（0-1，越高越好）"""
        # 早课惩罚
        if self.avoid_early_morning and start_section <= 2:
            return 0.3

        # 晚课惩罚
        if self.avoid_late_evening and start_section >= 9:
            return 0.3

        # 午餐时间惩罚
        if self.lunch_break_protection and start_section in [5, 6]:
            return 0.5

        # 黄金时间段（3-4节，7-8节）
        if start_section in [3, 4, 7, 8]:
            return 1.0

        # 其他时间段
        return 0.8

    def is_campus_conflict_allowed(
        self, campus1: str, campus2: str, time_gap: int
    ) -> bool:
        """检查校区冲突是否允许"""
        if campus1 == campus2:
            return True

        if self.campus_conflict_mode == CampusConflictMode.DISABLED:
            return True

        if self.campus_conflict_mode == CampusConflictMode.DAILY:
            return False

        if self.campus_conflict_mode == CampusConflictMode.PERIOD:
            return time_gap >= self.min_campus_transfer_time

        return False

    @staticmethod
    def get_default_config() -> "SchedulingConfig":
        """获取默认配置"""
        return SchedulingConfig()

    @staticmethod
    def get_strict_config() -> "SchedulingConfig":
        """获取严格配置（更多约束）"""
        return SchedulingConfig(
            campus_conflict_mode=CampusConflictMode.DAILY, max_credit_overflow_ratio=0.1
        )

    @staticmethod
    def get_flexible_config() -> "SchedulingConfig":
        """获取灵活配置（较少约束）"""
        return SchedulingConfig(
            campus_conflict_mode=CampusConflictMode.DISABLED,
            max_credit_overflow_ratio=0.3,
        )

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "campus_conflict_mode": self.campus_conflict_mode.value,
            "min_campus_transfer_time": self.min_campus_transfer_time,
            "credit_constraint_mode": self.credit_constraint_mode.value,
            "allow_credit_overflow": self.allow_credit_overflow,
            "max_credit_overflow_ratio": self.max_credit_overflow_ratio,
            "credit_gap_weight": self.credit_gap_weight,
            "avoid_early_morning": self.avoid_early_morning,
            "avoid_late_evening": self.avoid_late_evening,
            "lunch_break_protection": self.lunch_break_protection,
            "max_solve_time_seconds": self.max_solve_time_seconds,
            "max_solutions": self.max_solutions,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SchedulingConfig":
        """从字典创建配置对象"""
        return cls(
            campus_conflict_mode=CampusConflictMode(
                data.get("campus_conflict_mode", "daily")
            ),
            min_campus_transfer_time=data.get("min_campus_transfer_time", 2),
            credit_constraint_mode=CreditConstraintMode(
                data.get("credit_constraint_mode", "optimal")
            ),
            allow_credit_overflow=data.get("allow_credit_overflow", True),
            max_credit_overflow_ratio=data.get("max_credit_overflow_ratio", 0.2),
            credit_gap_weight=data.get("credit_gap_weight", 0.1),
            avoid_early_morning=data.get("avoid_early_morning", False),
            avoid_late_evening=data.get("avoid_late_evening", False),
            lunch_break_protection=data.get("lunch_break_protection", False),
            max_solve_time_seconds=data.get("max_solve_time_seconds", 30),
            max_solutions=data.get("max_solutions", 100),
        )
