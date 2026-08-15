#!/usr/bin/env python3
"""
排课约束检查器
实现各种约束条件的检查逻辑
"""

from typing import List, Dict, Tuple
from collections import defaultdict

from ..models import Course, SelectedCourse
from ..credit_manager import CreditManager
from .config import SchedulingConfig, CampusConflictMode
from .models import ConflictInfo


class ConstraintChecker:
    """约束检查器"""

    def __init__(self, config: SchedulingConfig, credit_manager: CreditManager):
        self.config = config
        self.credit_manager = credit_manager

    def check_all_constraints(
        self, selected_courses: List[SelectedCourse]
    ) -> Tuple[bool, List[ConflictInfo]]:
        """检查所有约束条件（向后兼容方法）"""
        return self.check_all_hard_constraints(selected_courses)

    def check_time_conflicts(
        self, selected_courses: List[SelectedCourse]
    ) -> List[ConflictInfo]:
        """检查时间冲突"""
        conflicts = []
        conflict_pairs = set()  # 用于避免重复冲突记录

        # 构建时间段占用表
        time_occupation = defaultdict(
            list
        )  # {(weekday, section, week): [selected_course, ...]}

        for selected_course in selected_courses:
            for time_slot in selected_course.time_slots:
                for week in time_slot.weeks:
                    for section in range(
                        time_slot.start_section, time_slot.end_section + 1
                    ):
                        key = (time_slot.weekday, section, week)
                        time_occupation[key].append(selected_course)

        # 检查冲突
        for key, courses in time_occupation.items():
            if len(courses) > 1:
                weekday, section, week = key
                for i in range(len(courses)):
                    for j in range(i + 1, len(courses)):
                        course1 = courses[i]
                        course2 = courses[j]

                        # 创建课程对标识符，避免重复记录同一对课程的冲突
                        pair_key = tuple(
                            sorted([course1.course.code, course2.course.code])
                        )

                        if pair_key not in conflict_pairs:
                            conflict_pairs.add(pair_key)
                            conflict = ConflictInfo(
                                conflict_type="time",
                                course1=course1.course,
                                course2=course2.course,
                                description=f"时间冲突：周{weekday}第{section}节第{week}周",
                                severity="high",
                            )
                            conflicts.append(conflict)

        return conflicts

    def check_campus_conflicts(
        self, selected_courses: List[SelectedCourse]
    ) -> List[ConflictInfo]:
        """检查校区冲突"""
        conflicts = []

        if self.config.campus_conflict_mode == CampusConflictMode.DISABLED:
            return conflicts

        # 按天分组检查
        daily_courses = defaultdict(
            list
        )  # {weekday: [(selected_course, time_slots), ...]}

        for selected_course in selected_courses:
            for time_slot in selected_course.time_slots:
                daily_courses[time_slot.weekday].append((selected_course, time_slot))

        # 检查每天的校区冲突
        for weekday, day_courses in daily_courses.items():
            if len(day_courses) <= 1:
                continue

            if self.config.campus_conflict_mode == CampusConflictMode.DAILY:
                # 日内模式：同一天不允许跨校区
                conflicts.extend(
                    self._check_daily_campus_conflicts(weekday, day_courses)
                )
            elif self.config.campus_conflict_mode == CampusConflictMode.PERIOD:
                # 时段模式：同时段内必须同校区
                conflicts.extend(
                    self._check_period_campus_conflicts(weekday, day_courses)
                )

        return conflicts

    def _check_daily_campus_conflicts(
        self, weekday: int, day_courses: List
    ) -> List[ConflictInfo]:
        """检查日内校区冲突"""
        conflicts = []

        # 收集所有校区
        campuses = set(course.course.campus for course, _ in day_courses)

        if len(campuses) > 1:
            # 找到第一个跨校区的课程对
            courses_by_campus = defaultdict(list)
            for course, slot in day_courses:
                courses_by_campus[course.course.campus].append((course, slot))

            campus_list = list(campuses)
            for i in range(len(campus_list)):
                for j in range(i + 1, len(campus_list)):
                    campus1, campus2 = campus_list[i], campus_list[j]
                    course1 = courses_by_campus[campus1][0][0]
                    course2 = courses_by_campus[campus2][0][0]

                    conflict = ConflictInfo(
                        conflict_type="campus",
                        course1=course1.course,
                        course2=course2.course,
                        description=f"校区冲突：{campus1} -> {campus2}（日内模式不允许跨校区）",
                        severity="high",
                    )
                    conflicts.append(conflict)
                    break  # 只报告一个冲突即可
                if conflicts:
                    break

        return conflicts

    def _check_period_campus_conflicts(
        self, weekday: int, day_courses: List
    ) -> List[ConflictInfo]:
        """同一半天时段内不得跨校区（考虑周次重叠）。

        转场能不能赶上，取决于两节课之间有没有午休 / 晚饭，
        而不是隔了几节。节次编号是等距整数，表达不了这个断点：

        * 1-2 节 → 3-4 节：课间 10 分铟，同属上午 → 赶不到
        * 3-4 节 → 5-6 节：隔着午休，上午→下午 → 赶得到
        * 7-8 节 → 9-10 节：隔着晚饭，下午→晚上 → 赶得到

        三种情况的“空出节数”都是 0，所以改用 config.half_day_blocks
        判定是否同块；同块且跨校区即为冲突。
        """
        conflicts = []

        for i in range(len(day_courses)):
            for j in range(i + 1, len(day_courses)):
                course1, slot1 = day_courses[i]
                course2, slot2 = day_courses[j]

                # 同校区无需转场
                if course1.course.campus == course2.course.campus:
                    continue

                # 必须周次重叠才会真实冲突
                weeks_overlap = set(slot1.weeks) & set(slot2.weeks)
                if not weeks_overlap:
                    continue

                blocks1 = self.config.blocks_for_range(
                    slot1.start_section, slot1.end_section
                )
                blocks2 = self.config.blocks_for_range(
                    slot2.start_section, slot2.end_section
                )
                shared_blocks = blocks1 & blocks2
                if not shared_blocks:
                    continue  # 跳块 → 有午休/晚饭可用于转场

                overlap_weeks = sorted(weeks_overlap)
                weeks_str = (
                    f"{overlap_weeks[0]}-{overlap_weeks[-1]}周"
                    if len(overlap_weeks) > 1
                    else f"{overlap_weeks[0]}周"
                )
                block_str = "、".join(sorted(shared_blocks))

                conflict = ConflictInfo(
                    conflict_type="campus",
                    course1=course1.course,
                    course2=course2.course,
                    description=(
                        f"同一时段跨校区：{course1.course.campus} -> {course2.course.campus}"
                        f"（均在{block_str}，第{slot1.start_section}-{slot1.end_section}节 与 "
                        f"第{slot2.start_section}-{slot2.end_section}节，{weeks_str}）"
                    ),
                    # 搜索阶段就把它当硬约束拒掉（engine._is_campus_compatible）。
                    # 此处必须同为 high，否则 check_all_hard_constraints 只统计
                    # high，会把一个真实的跨校区冲突当成“有效方案”放过。
                    severity="high",
                )
                conflicts.append(conflict)

        return conflicts

    def check_credit_constraints(
        self, selected_courses: List[SelectedCourse]
    ) -> List[ConflictInfo]:
        """检查学分约束（支持严格/灵活两种模式）"""
        conflicts = []

        # 计算各类别学分
        category_credits = defaultdict(float)
        for selected_course in selected_courses:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            category_credits[category] += credits

        # 检查学分要求。actual_credits 必须包含用户设置的基础已修学分，
        # 与引擎的 gap = required - completed 语义保持一致。
        for category, requirement in self.credit_manager.requirements.items():
            actual_credits = (
                category_credits.get(category, 0.0)
                + requirement.completed_credits
            )
            required_credits = requirement.required_credits

            if actual_credits < required_credits:
                # 根据配置模式决定冲突严重程度
                if self.config.credit_constraint_mode.value == "required":
                    # 必需模式：学分不足是高严重程度冲突（硬约束）
                    severity = "high"
                    conflict_type = "credit_insufficient_required"
                else:
                    # 优化模式：学分不足是中等严重程度冲突（软约束）
                    severity = "medium"
                    conflict_type = "credit_insufficient_optimal"

                gap = required_credits - actual_credits
                conflict = ConflictInfo(
                    conflict_type=conflict_type,
                    course1=None,
                    course2=None,
                    description=f"{category}学分不足：需要{required_credits:.1f}，实际{actual_credits:.1f}，缺口{gap:.1f}",
                    severity=severity,
                )
                conflicts.append(conflict)

        return conflicts

    def check_course_mutual_exclusion(
        self, selected_courses: List[SelectedCourse]
    ) -> List[ConflictInfo]:
        """检查同一课程不同班次的互斥约束（硬约束）"""
        conflicts = []

        # 按课程编码分组
        course_groups = defaultdict(list)
        for selected_course in selected_courses:
            course_code = selected_course.course.code
            course_groups[course_code].append(selected_course)

        # 检查每个课程组是否有多个班次被选择
        for course_code, courses_in_group in course_groups.items():
            if len(courses_in_group) > 1:
                # 同一课程的多个班次被选择，这是违反互斥约束的
                course_name = courses_in_group[0].course.name

                # 为每对冲突的班次创建冲突信息
                for i in range(len(courses_in_group)):
                    for j in range(i + 1, len(courses_in_group)):
                        course1 = courses_in_group[i]
                        course2 = courses_in_group[j]

                        conflict = ConflictInfo(
                            conflict_type="course_mutual_exclusion",
                            course1=course1.course,
                            course2=course2.course,
                            description=f"同一课程多班次冲突：{course_name} (班次{course1.class_num}与班次{course2.class_num})",
                            severity="high",  # 这是硬约束，必须满足
                        )
                        conflicts.append(conflict)

        return conflicts

    def check_credit_efficiency_constraints(
        self, selected_courses: List[SelectedCourse], available_courses: List[Course]
    ) -> List[ConflictInfo]:
        """检查学分效率约束（硬约束）"""
        conflicts = []

        # 计算各类别当前学分
        category_credits = defaultdict(float)
        for selected_course in selected_courses:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            category_credits[category] += credits

        # 检查是否有不必要的超出
        for category, requirement in self.credit_manager.requirements.items():
            actual_credits = category_credits.get(category, 0.0)
            required_credits = requirement.required_credits

            if actual_credits > required_credits:
                # 检查是否为必要超出
                # 获取该类别的剩余可选课程
                remaining_courses = [
                    c
                    for c in available_courses
                    if c.category == category
                    and not any(sc.course.code == c.code for sc in selected_courses)
                ]

                if remaining_courses:
                    # 找到最小学分的课程
                    min_credits = min(c.credits for c in remaining_courses)

                    # 如果当前学分减去最小学分课程仍然满足要求，则为不必要超出
                    if actual_credits - min_credits >= required_credits:
                        conflict = ConflictInfo(
                            conflict_type="credit_unnecessary_overflow",
                            course1=None,
                            course2=None,
                            description=f"{category}存在不必要的学分超出：实际{actual_credits:.1f}，需要{required_credits:.1f}",
                            severity="high",
                        )
                        conflicts.append(conflict)

        return conflicts

    def check_all_hard_constraints(
        self,
        selected_courses: List[SelectedCourse],
        available_courses: List[Course] = None,
    ) -> Tuple[bool, List[ConflictInfo]]:
        """检查所有硬约束条件"""
        conflicts = []

        # 检查基本硬约束
        time_conflicts = self.check_time_conflicts(selected_courses)
        campus_conflicts = self.check_campus_conflicts(selected_courses)
        credit_conflicts = self.check_credit_constraints(selected_courses)

        # 检查同一课程不同班次互斥约束（新增的关键硬约束）
        mutual_exclusion_conflicts = self.check_course_mutual_exclusion(
            selected_courses
        )

        conflicts.extend(time_conflicts)
        conflicts.extend(campus_conflicts)
        conflicts.extend(credit_conflicts)
        conflicts.extend(mutual_exclusion_conflicts)

        # 检查学分效率约束（如果提供了可选课程列表）
        if available_courses:
            efficiency_conflicts = self.check_credit_efficiency_constraints(
                selected_courses, available_courses
            )
            conflicts.extend(efficiency_conflicts)

        # 硬约束是否全部满足
        hard_constraints_satisfied = (
            len([c for c in conflicts if c.severity == "high"]) == 0
        )

        return hard_constraints_satisfied, conflicts

    def is_valid_schedule(
        self,
        selected_courses: List[SelectedCourse],
        available_courses: List[Course] = None,
    ) -> bool:
        """检查排课方案是否有效（仅检查硬约束）"""
        hard_constraints_satisfied, _ = self.check_all_hard_constraints(
            selected_courses, available_courses
        )
        return hard_constraints_satisfied

    def get_constraint_violations_count(
        self,
        selected_courses: List[SelectedCourse],
        available_courses: List[Course] = None,
    ) -> Dict[str, int]:
        """获取各类约束违反次数"""
        _, conflicts = self.check_all_hard_constraints(
            selected_courses, available_courses
        )

        violation_counts = defaultdict(int)
        for conflict in conflicts:
            violation_counts[conflict.conflict_type] += 1

        return dict(violation_counts)
