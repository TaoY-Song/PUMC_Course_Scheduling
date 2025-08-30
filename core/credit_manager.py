#!/usr/bin/env python3
"""
学分管理模块
管理各类别课程的学分要求和完成情况
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CreditRequirement:
    """单个类别的学分要求"""

    category_name: str  # 类别名称
    required_credits: float  # 要求学分
    completed_credits: float = 0.0  # 已修学分（总计，包括基础学分和算法添加的学分）
    base_completed_credits: float = 0.0  # 用户手动设置的基础已修学分

    @property
    def remaining_credits(self) -> float:
        """未修学分（要求学分 - 已修学分，最小为0）"""
        return max(0.0, self.required_credits - self.completed_credits)

    @property
    def completion_rate(self) -> float:
        """完成率（0-1）"""
        if self.required_credits <= 0:
            return 1.0
        return min(1.0, self.completed_credits / self.required_credits)

    @property
    def is_completed(self) -> bool:
        """是否已完成要求"""
        return self.completed_credits >= self.required_credits

    def set_completed_credits(self, credits: float):
        """设置已修学分"""
        self.completed_credits = max(0.0, credits)


class CreditManager:
    """学分管理器"""

    # 默认学分要求
    DEFAULT_REQUIREMENTS = {
        "公共必修课 - 公共必修": 4.0,
        "公共必修课 - 公共必修（二选一）": 1.0,
        "选修课 - 限制性选修": 1.0,
        "选修课 - 通识选修": 1.0,
        "选修课 - 学位选修": 8.0,
        "学位必修课（核心课）": 11.0,
    }

    def __init__(self):
        self.requirements: Dict[str, CreditRequirement] = {}
        self._initialize_requirements()

        # 🔧 调试：验证初始化状态
        print("🔍 [调试] CreditManager初始化完成")
        for category, req in self.requirements.items():
            if req.completed_credits > 0 or req.base_completed_credits > 0:
                print(
                    f"⚠️ [调试] 发现非零学分: {category} - completed:{req.completed_credits}, base:{req.base_completed_credits}"
                )
            else:
                print(
                    f"✅ [调试] 正常初始状态: {category} - completed:{req.completed_credits}, base:{req.base_completed_credits}"
                )

    def _initialize_requirements(self):
        """初始化默认学分要求"""
        for category, credits in self.DEFAULT_REQUIREMENTS.items():
            self.requirements[category] = CreditRequirement(
                category_name=category, required_credits=credits
            )

    def get_requirement(self, category: str) -> Optional[CreditRequirement]:
        """获取指定类别的学分要求"""
        return self.requirements.get(category)

    def add_requirement(self, category: str, requirement: CreditRequirement) -> bool:
        """添加新的学分要求"""
        if category and requirement:
            self.requirements[category] = requirement
            return True
        return False

    def set_required_credits(self, category: str, credits: float) -> bool:
        """设置指定类别的要求学分"""
        if category in self.requirements and credits >= 0:
            self.requirements[category].required_credits = credits
            return True
        return False

    def set_completed_credits(self, category: str, credits: float) -> bool:
        """设置指定类别的已修学分（用户手动设置的基础学分）"""
        if category in self.requirements and credits >= 0:
            self.requirements[category].base_completed_credits = credits
            self.requirements[category].completed_credits = credits
            return True
        return False

    def add_completed_credits(self, category: str, credits: float):
        """添加已修学分"""
        if category in self.requirements:
            current_completed = self.requirements[category].completed_credits
            self.requirements[category].set_completed_credits(
                current_completed + credits
            )
        else:
            # 如果类别不存在，创建新的要求
            self.requirements[category] = CreditRequirement(
                category_name=category, required_credits=0.0, completed_credits=credits
            )

    def get_total_required_credits(self) -> float:
        """获取总要求学分"""
        return sum(req.required_credits for req in self.requirements.values())

    def get_total_completed_credits(self) -> float:
        """获取总已修学分"""
        return sum(req.completed_credits for req in self.requirements.values())

    def get_total_remaining_credits(self) -> float:
        """获取总剩余学分"""
        return sum(req.remaining_credits for req in self.requirements.values())

    def get_overall_completion_rate(self) -> float:
        """获取总体完成率"""
        total_required = self.get_total_required_credits()
        if total_required <= 0:
            return 1.0
        return min(1.0, self.get_total_completed_credits() / total_required)

    def get_categories_summary(self) -> List[Dict]:
        """获取各类别摘要信息"""
        summary = []
        for category, req in self.requirements.items():
            summary.append(
                {
                    "category": category,
                    "required": req.required_credits,
                    "completed": req.completed_credits,
                    "remaining": req.remaining_credits,
                    "completion_rate": req.completion_rate,
                    "is_completed": req.is_completed,
                }
            )
        return summary

    def reset_completed_credits(self):
        """重置所有已修学分为0"""
        for req in self.requirements.values():
            req.completed_credits = 0.0

    def get_category_status_text(self, category: str) -> str:
        """获取类别状态文本"""
        req = self.get_requirement(category)
        if not req:
            return "未知类别"

        status = f"{req.completed_credits:.1f}/{req.required_credits:.1f}"
        if req.is_completed:
            status += " ✓"
        else:
            status += f" (还需{req.remaining_credits:.1f})"

        return status
