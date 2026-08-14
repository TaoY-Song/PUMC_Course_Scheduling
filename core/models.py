#!/usr/bin/env python3
"""
核心数据模型定义
包含Course、TimeSlot、SelectedCourse等核心数据类
"""

from dataclasses import dataclass
from typing import List

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Course:
    """课程数据类"""

    code: str  # 课程编码
    name: str  # 课程名称
    department: str  # 开课院系
    category: str  # 课程类别
    class_num: int  # 班次
    campus: str  # 校区
    teacher: str  # 任课教师
    credits: float  # 学分
    hours: float  # 学时
    description: str = ""  # 选课说明
    is_online: bool = False  # 是否线上课程
    custom_category: str = ""  # 自定义类别（从Excel的"自定义类别"列读取）

    def __str__(self):
        return f"{self.code} - {self.name} ({self.teacher}, {self.credits}学分)"

    def get_basic_info(self):
        """获取基本信息字符串"""
        return f"{self.campus} | {self.hours}学时"

    def get_full_info(self):
        """获取完整信息"""
        info = (
            f"{self.code} - {self.name}\n"
            f"  教师: {self.teacher} | 校区: {self.campus} | 学分: {self.credits}\n"
            f"  学时: {self.hours} | 开课院系: {self.department}\n"
            f"  类别: {self.category}"
        )

        if self.description and self.description.strip() and self.description != "nan":
            # 截取说明的前100个字符
            desc = (
                self.description[:100] + "..."
                if len(self.description) > 100
                else self.description
            )
            info += f"\n  说明: {desc}"

        return info


@dataclass
class TimeSlot:
    """时间段"""

    weekday: int  # 星期几 (1-7)
    start_section: int  # 开始节次 (1-10)
    end_section: int  # 结束节次 (1-10)
    weeks: List[int]  # 上课周次列表

    def __str__(self):
        weekday_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weeks_str = self._format_weeks()
        return f"{weekday_names[self.weekday]} {self.start_section}-{self.end_section}节 ({weeks_str})"

    def _format_weeks(self) -> str:
        """格式化周次显示"""
        if not self.weeks:
            return "无"

        # 找连续的周次
        ranges = []
        start = self.weeks[0]
        end = start

        for i in range(1, len(self.weeks)):
            if self.weeks[i] == end + 1:
                end = self.weeks[i]
            else:
                if start == end:
                    ranges.append(f"{start}")
                else:
                    ranges.append(f"{start}-{end}")
                start = end = self.weeks[i]

        # 添加最后一个范围
        if start == end:
            ranges.append(f"{start}")
        else:
            ranges.append(f"{start}-{end}")

        return f"{','.join(ranges)}周"


@dataclass
class SelectedCourse:
    """已选择的课程（包含时间安排）"""

    course: Course
    class_num: int  # 选择的班次
    time_slots: List[TimeSlot] = None  # 时间安排列表
    is_online: bool = False  # 是否线上课程
    custom_category: str = ""  # 用户设置的课程类别
    is_imported: bool = False  # 是否为导入的课程（影响类别选择选项）

    def __post_init__(self):
        if self.time_slots is None:
            self.time_slots = []

        # 优先使用Course对象中的custom_category（从Excel文件读取的）
        if not self.custom_category or str(self.custom_category).lower() in [
            "nan",
            "none",
        ]:
            if (
                hasattr(self.course, "custom_category")
                and self.course.custom_category
                and str(self.course.custom_category).lower() not in ["nan", "none", ""]
            ):
                self.custom_category = self.course.custom_category
                logger.debug(
                    f"   📋 使用Excel中的自定义类别: {self.course.code} -> {self.custom_category}"
                )
            else:
                self.custom_category = self._auto_assign_category()
                logger.debug(
                    f"   🔄 自动分配类别: {self.course.code} -> {self.custom_category}"
                )

    def _auto_assign_category(self) -> str:
        """根据原始课程类别自动分配新类别"""
        original_category = self.course.category

        # 自动转换规则 - 导入的课程会设置is_imported=True，获得确定的类别
        if "限制选修" in original_category:
            return "选修课 - 限制性选修"
        elif "通识选修" in original_category:
            return "选修课 - 通识选修"
        elif "学位选修" in original_category:
            return "选修课 - 学位选修"
        elif "学位专业" in original_category or "核心课" in original_category:
            return "学位必修课（核心课）"
        elif "公共必修" in original_category:
            # 公共必修课需要用户手动选择具体类型
            return "nan"  # 可选类型，默认显示nan提醒用户设置
        else:
            # 对于其他未知类别，尝试智能推测
            if "必修" in original_category:
                return "学位必修课（核心课）"
            elif "选修" in original_category:
                return "选修课 - 学位选修"
            else:
                return "nan"  # 可选类型，默认显示nan提醒用户设置

    def get_available_categories(self) -> List[str]:
        """获取可选的课程类别列表"""
        # 根据课程的原始类别返回对应的可选类别（导入和手动添加的课程都遵循相同规则）
        original_category = self.course.category

        # 通识选修课：只能选择通识选修
        if "通识选修" in original_category:
            return ["选修课 - 通识选修"]
        # 限制性选修课：只能选择限制性选修
        elif "限制选修" in original_category:
            return ["选修课 - 限制性选修"]
        elif "公共必修" in original_category:
            return ["公共必修课 - 公共必修", "公共必修课 - 公共必修（二选一）"]
        else:
            return ["选修课 - 学位选修", "学位必修课（核心课）"]

    def set_custom_category(self, category: str) -> bool:
        """设置自定义课程类别（支持任意有效输入）"""
        # 验证输入不为空且不是无效值
        if (
            not category
            or not category.strip()
            or category.strip().lower() in ["nan", "none"]
        ):
            return False

        # 允许设置任意非空的类别名称
        self.custom_category = category.strip()
        return True

    @staticmethod
    def has_time_conflict(course1: "SelectedCourse", course2: "SelectedCourse") -> bool:
        """检查两门课程是否有时间冲突（统一的工具方法）"""
        for slot1 in course1.time_slots:
            for slot2 in course2.time_slots:
                if (
                    slot1.weekday == slot2.weekday
                    and set(range(slot1.start_section, slot1.end_section + 1))
                    & set(range(slot2.start_section, slot2.end_section + 1))
                    and set(slot1.weeks) & set(slot2.weeks)
                ):
                    return True
        return False
