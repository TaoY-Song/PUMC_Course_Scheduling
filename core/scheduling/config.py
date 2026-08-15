#!/usr/bin/env python3
"""
排课算法配置管理
定义排课过程中的各种配置选项和约束参数
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


#: 半天时段划分（节次区间闭区间，含两端）。
#
#: 跨校区转场的真实约束不是“隔几节”，而是“中间有没有午休 / 晚饭”。
#: 节次编号是等距整数，看不出这个断点：2→3〔课间 10 分〕与
#: 4→5〔午休〕在节次上都是“相邻”，但前者赶不到、后者赶得到。
#: 所以用时段块表达：**同一块内禁止跨校区，跳块则允许**。
#:
#: 默认按常见作息（1-4 上午、5-8 下午、9-10 晚上）。
#: 作息不同的学校改这一处即可，不需动约束逻辑。
DEFAULT_HALF_DAY_BLOCKS: Tuple[Tuple[str, int, int], ...] = (
    ("上午", 1, 4),
    ("下午", 5, 8),
    ("晚上", 9, 10),
)


class CampusConflictMode(Enum):
    """校区冲突处理模式"""

    DAILY = "daily"  # 日内模式：同一天不允许跨校区
    PERIOD = "period"  # 时段模式：同一半天时段内不允许跨校区，跳时段允许
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
    # 每组校区在冲突判断中视为同一校区，课程原始校区名称不改。
    campus_equivalence_groups: Tuple[Tuple[str, ...], ...] = ()
    #: 半天时段划分，PERIOD 模式用它判定“是不是同一块”。
    half_day_blocks: Tuple[Tuple[str, int, int], ...] = DEFAULT_HALF_DAY_BLOCKS

    # 学分约束配置
    credit_constraint_mode: CreditConstraintMode = (
        CreditConstraintMode.OPTIMAL
    )  # 学分约束模式（与UI默认保持一致）
    allow_credit_overflow: bool = True  # 是否允许学分超出要求
    # 溢出上限用固定学分而不是比例。比例制在小缺口上张不开：
    # 限选要求 1.0 分、ratio=0.2 时上限只有 1.2，连一门 1.5 分的课都收不下；
    # 而培养方案写的是「总学分 >=1 学分」，只有下限没有上限。
    max_credit_overflow: float = 1.0  # 每类别允许超出的学分数
    # 某类别一门都没选中时，允许突破溢出上限收下一门。
    # 用户把课放进候选池就是想修它；该类 0 学分比溢出 0.5 分更糟。
    rescue_empty_category: bool = True
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

        seen_campuses = {}
        for group_index, group in enumerate(self.campus_equivalence_groups, start=1):
            if len(group) < 2:
                errors.append(f"等价校区组 {group_index} 至少需要两个校区")
            for campus in group:
                if campus in seen_campuses and seen_campuses[campus] != group_index:
                    errors.append(f"校区「{campus}」不能同时属于多个等价组")
                seen_campuses[campus] = group_index

        # 验证时段划分
        if not self.half_day_blocks:
            errors.append("半天时段划分不能为空")
        for label, start, end in self.half_day_blocks:
            if start > end:
                errors.append(f"时段「{label}」的起始节次不能大于结束节次")
            if start < 1:
                errors.append(f"时段「{label}」的起始节次必须不小于 1")

        # 验证学分超出上限
        if self.max_credit_overflow < 0:
            errors.append("学分超出上限不能为负数")

        # 验证学分缺口权重
        if self.credit_gap_weight < 0:
            errors.append("学分缺口权重不能为负数")

        # 验证求解器配置
        if self.max_solve_time_seconds <= 0:
            errors.append("最大求解时间应大于0")

        if self.max_solutions <= 0:
            errors.append("最大解数量应大于0")

        return errors

    def normalize_campus(self, campus: Optional[str]) -> str:
        """返回用于冲突和评分比较的校区值。"""
        value = (campus or "").strip()
        for group in self.campus_equivalence_groups:
            if value in group:
                return group[0]
        return value

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

    def block_label_for_section(self, section: int) -> Optional[str]:
        """返回节次所属半天时段的名称；不属于任何块时返回 None。"""
        for label, start, end in self.half_day_blocks:
            if start <= section <= end:
                return label
        return None

    def blocks_for_range(self, start_section: int, end_section: int) -> set:
        """返回一段课占用的所有半天时段名称。

        跨块的课（例如 4-5 节横跨午休）会同时占两个块，
        这时它与上午、下午的课都算同块——因为人确实在那两段时间里。
        落在定义外的节次归到 ``"其他"``，不静默当成无冲突。
        """
        blocks = set()
        for section in range(start_section, end_section + 1):
            blocks.add(self.block_label_for_section(section) or "其他")
        return blocks

    @staticmethod
    def get_default_config() -> "SchedulingConfig":
        """获取默认配置"""
        return SchedulingConfig()

    @staticmethod
    def get_strict_config() -> "SchedulingConfig":
        """获取严格配置（更多约束）"""
        return SchedulingConfig(
            campus_conflict_mode=CampusConflictMode.DAILY, max_credit_overflow=0.5
        )

    @staticmethod
    def get_flexible_config() -> "SchedulingConfig":
        """获取灵活配置（较少约束）"""
        return SchedulingConfig(
            campus_conflict_mode=CampusConflictMode.DISABLED,
            max_credit_overflow=2.0,
        )

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "campus_conflict_mode": self.campus_conflict_mode.value,
            "campus_equivalence_groups": [list(group) for group in self.campus_equivalence_groups],
            "half_day_blocks": [list(block) for block in self.half_day_blocks],
            "credit_constraint_mode": self.credit_constraint_mode.value,
            "allow_credit_overflow": self.allow_credit_overflow,
            "max_credit_overflow": self.max_credit_overflow,
            "rescue_empty_category": self.rescue_empty_category,
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
        raw_groups = data.get("campus_equivalence_groups") or []
        equivalence_groups = tuple(
            tuple(dict.fromkeys(str(campus).strip() for campus in group if str(campus).strip()))
            for group in raw_groups
            if isinstance(group, (list, tuple))
        )
        raw_blocks = data.get("half_day_blocks")
        blocks = (
            tuple((str(label), int(start), int(end)) for label, start, end in raw_blocks)
            if raw_blocks
            else DEFAULT_HALF_DAY_BLOCKS
        )
        return cls(
            campus_conflict_mode=CampusConflictMode(
                data.get("campus_conflict_mode", "daily")
            ),
            campus_equivalence_groups=equivalence_groups,
            half_day_blocks=blocks,
            credit_constraint_mode=CreditConstraintMode(
                data.get("credit_constraint_mode", "optimal")
            ),
            allow_credit_overflow=data.get("allow_credit_overflow", True),
            max_credit_overflow=data.get("max_credit_overflow", 1.0),
            rescue_empty_category=data.get("rescue_empty_category", True),
            credit_gap_weight=data.get("credit_gap_weight", 0.1),
            avoid_early_morning=data.get("avoid_early_morning", False),
            avoid_late_evening=data.get("avoid_late_evening", False),
            lunch_break_protection=data.get("lunch_break_protection", False),
            max_solve_time_seconds=data.get("max_solve_time_seconds", 30),
            max_solutions=data.get("max_solutions", 100),
        )
