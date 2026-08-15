#!/usr/bin/env python3
"""
排课方案评估器
对生成的排课方案进行评分和排序
"""

from typing import List, Dict
from collections import defaultdict
import math

from ..models import SelectedCourse
from .config import SchedulingConfig
from .models import ScheduleScore, ScheduleResult

from ..logging_config import get_logger

logger = get_logger(__name__)


class ScheduleEvaluator:
    """排课方案评估器"""

    def __init__(self, config: SchedulingConfig):
        self.config = config

    def evaluate_schedule(
        self, selected_courses: List[SelectedCourse], credit_manager=None, config=None
    ) -> ScheduleScore:
        """评估排课方案（修正的评分机制）"""
        score = ScheduleScore()

        if not selected_courses:
            return score

        # 关键修正：评分逻辑应该是先检查硬约束，满足了给100分，然后扣分
        # 这里假设传入的selected_courses已经满足硬约束（由排课引擎保证）
        # 如果不满足硬约束，分数为0
        score.hard_constraints_satisfied = True  # 由调用者设置

        if not score.hard_constraints_satisfied:
            score.total_score = 0.0
            score.credit_efficiency_score = 0.0
            return score

        # 满足硬约束的情况下，基于时间质量评分
        time_quality_score = self._calculate_time_quality_score(selected_courses)

        # 🔧 修正：增加学分匹配度评分的权重，确保学分匹配度是主要评分因素
        credit_match_score = self._calculate_credit_match_score(
            selected_courses, credit_manager
        )

        # 计算学分相关的惩罚（权重适中）
        overflow_penalty = (
            self._calculate_credit_overflow_penalty(selected_courses, credit_manager)
            * 0.5
        )
        gap_penalty = 0.0
        if config and config.credit_constraint_mode.value == "optimal":
            gap_penalty = (
                self._calculate_credit_gap_penalty(
                    selected_courses, credit_manager, config
                )
                * 0.5
            )

        # 🔧 修正：最终分数计算 - 学分匹配度权重更高
        # 学分匹配度占70%，时间质量占30%
        # 🔧 P1 修复：限幅到 0-100，与字段声明的“总分（0-100）”一致。
        score.total_score = min(
            100.0,
            max(
                0.0,
                credit_match_score * 0.7
                + time_quality_score * 0.3
                - overflow_penalty
                - gap_penalty,
            ),
        )
        score.credit_efficiency_score = credit_match_score

        # 🔧 P1 修复：以前只赋值 total_score 和 credit_efficiency_score，
        # time_preference_score / campus_consistency_score /
        # course_distribution_score 三个字段永远保持 0.0，
        # 导致 Web DTO 里的 time_quality_score 恒为 0。
        score.time_preference_score = time_quality_score
        score.campus_consistency_score = self._calculate_campus_consistency_score(
            selected_courses
        )
        score.course_distribution_score = self._calculate_course_distribution_score(
            selected_courses
        )

        return score

    def _calculate_credit_match_score(
        self, selected_courses: List[SelectedCourse], credit_manager
    ) -> float:
        """计算学分匹配度评分（新增方法）"""
        if not credit_manager or not selected_courses:
            return 0.0

        # 计算各类别的实际学分
        category_credits = defaultdict(float)
        for sc in selected_courses:
            category_credits[sc.custom_category] += sc.course.credits

        # 获取学分要求
        requirements = credit_manager.requirements
        total_match_score = 0.0
        total_categories = 0

        for category, requirement in requirements.items():
            if requirement.required_credits > 0:  # 只考虑有要求的类别
                actual_credits = (
                    category_credits.get(category, 0.0) + requirement.completed_credits
                )
                required_credits = requirement.required_credits

                # 计算匹配度评分
                if actual_credits == required_credits:
                    # 完美匹配：100分
                    match_score = 100.0
                elif actual_credits < required_credits:
                    # 不足：按比例给分，最低20分
                    ratio = actual_credits / required_credits
                    match_score = max(20.0, ratio * 80.0)
                else:
                    # 超出：根据超出程度扣分
                    overflow = actual_credits - required_credits
                    if overflow <= 1.0:
                        match_score = 95.0  # 轻微超出，扣5分
                    elif overflow <= 2.0:
                        match_score = 85.0  # 中等超出，扣15分
                    else:
                        match_score = max(
                            50.0, 85.0 - (overflow - 2.0) * 10.0
                        )  # 严重超出，大幅扣分

                total_match_score += match_score
                total_categories += 1

                logger.debug(
                    f"   📊 学分匹配评分 {category}: {actual_credits:.1f}/{required_credits:.1f} = {match_score:.1f}分"
                )

        # 返回平均匹配度评分
        average_score = (
            total_match_score / total_categories if total_categories > 0 else 0.0
        )
        logger.debug(f"   🎯 总体学分匹配评分: {average_score:.1f}分")
        return average_score

    def _calculate_time_efficiency_score(
        self, selected_courses: List[SelectedCourse], credit_manager
    ) -> float:
        """计算时间效率评分（主要目标）"""
        if not credit_manager or not selected_courses:
            return 0.0

        # 计算各类别学分
        category_credits = defaultdict(float)
        category_completion_weeks = defaultdict(lambda: 20)  # 默认20周完成

        for selected_course in selected_courses:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            category_credits[category] += credits

            # 计算完成周次（简化：假设所有课程在第8周完成）
            if selected_course.time_slots:
                # 有时间安排的课程，取最大周次
                max_week = 8  # 简化假设
                if category_completion_weeks[category] > max_week:
                    category_completion_weeks[category] = max_week
            else:
                # 线上课程，假设可以立即完成
                category_completion_weeks[category] = 1

        # 计算时间效率分数
        total_efficiency = 0.0
        total_weight = 0.0

        for category, requirement in credit_manager.requirements.items():
            actual_credits = category_credits.get(category, 0.0)
            required_credits = requirement.required_credits
            completion_week = category_completion_weeks.get(category, 20)

            if actual_credits >= required_credits:
                # 已满足要求，计算时间效率
                # 越早完成分数越高：(21 - completion_week) / 20 * 100
                efficiency = (21 - completion_week) / 20 * 100
            else:
                # 未满足要求，根据完成度给分
                completion_ratio = (
                    actual_credits / required_credits if required_credits > 0 else 0
                )
                efficiency = completion_ratio * 50  # 最高50分

            weight = required_credits  # 以要求学分作为权重
            total_efficiency += efficiency * weight
            total_weight += weight

        return (total_efficiency / total_weight) if total_weight > 0 else 0.0

    def _calculate_credit_satisfaction_score(
        self, selected_courses: List[SelectedCourse], credit_manager
    ) -> float:
        """计算学分满足度评分"""
        if not credit_manager or not selected_courses:
            return 0.0

        # 计算各类别学分
        category_credits = defaultdict(float)
        for selected_course in selected_courses:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            category_credits[category] += credits

        # 计算满足度
        total_satisfaction = 0.0
        total_weight = 0.0

        for category, requirement in credit_manager.requirements.items():
            actual_credits = category_credits.get(category, 0.0)
            required_credits = requirement.required_credits

            # 满足度 = min(1, 实际学分/要求学分)
            satisfaction = min(
                1.0, actual_credits / required_credits if required_credits > 0 else 1.0
            )
            weight = required_credits  # 以要求学分作为权重

            total_satisfaction += satisfaction * weight
            total_weight += weight

        return (total_satisfaction / total_weight * 100) if total_weight > 0 else 0.0

    def _calculate_credit_overflow_penalty(
        self, selected_courses: List[SelectedCourse], credit_manager
    ) -> float:
        """计算学分超出惩罚"""
        if not credit_manager or not selected_courses:
            return 0.0

        # 计算各类别学分
        category_credits = defaultdict(float)
        for selected_course in selected_courses:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            category_credits[category] += credits

        # 计算超出惩罚
        total_overflow = 0.0

        for category, requirement in credit_manager.requirements.items():
            actual_credits = (
                category_credits.get(category, 0.0)
                + requirement.completed_credits
            )
            required_credits = requirement.required_credits

            if actual_credits > required_credits:
                overflow = actual_credits - required_credits
                total_overflow += overflow * 2  # 每超出1学分惩罚2分

        return total_overflow

    def _calculate_credit_gap_penalty(
        self, selected_courses: List[SelectedCourse], credit_manager, config
    ) -> float:
        """计算学分缺口惩罚（优化模式下使用）"""
        if not credit_manager or not selected_courses:
            return 0.0

        # 计算各类别学分
        category_credits = defaultdict(float)
        for selected_course in selected_courses:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            category_credits[category] += credits

        # 计算学分缺口惩罚
        total_gap_penalty = 0.0

        for category, requirement in credit_manager.requirements.items():
            actual_credits = (
                category_credits.get(category, 0.0)
                + requirement.completed_credits
            )
            required_credits = requirement.required_credits

            if actual_credits < required_credits:
                # 计算学分缺口
                gap = required_credits - actual_credits
                # 简化缺口惩罚计算，移除类别权重放大，避免过度惩罚
                gap_penalty = gap * config.credit_gap_weight
                total_gap_penalty += gap_penalty

        return total_gap_penalty

    def _calculate_time_quality_score(
        self, selected_courses: List[SelectedCourse]
    ) -> float:
        """计算时间质量评分

        评分逻辑：
        1. 基础分：100分（满足硬约束的前提下）
        2. 时段偏好惩罚：依据 config 的时间偏好设置扣分
        3. 课程分布奖励：课程分布越均匀得分越高

        🔧 P1 修复：
        - 之前本方法用硬编码阈值判早/晚课，完全忽略
          config.get_time_preference_score()，导致 avoid_early_morning /
          avoid_late_evening / lunch_break_protection 三个配置改了也不生效。
        - 且分布奖励可以把分数推到 100 以上（实测 108），
          与“0-100 分”的字段语义矛盾。现在限幅到 100。
        """
        if not selected_courses:
            return 0.0

        base_score = 100.0
        penalty = 0.0

        # 统计每天的课程分布
        daily_courses = defaultdict(list)

        # 分析每门课程的时间特征
        for selected_course in selected_courses:
            worst_preference = 1.0  # 1.0 表示最佳时段

            for time_slot in selected_course.time_slots:
                daily_courses[time_slot.weekday].append(selected_course)

                # 使用配置的时间偏好评分（受 avoid_early_morning 等开关影响）
                preference = self.config.get_time_preference_score(
                    time_slot.start_section
                )
                worst_preference = min(worst_preference, preference)

            # 偏好度越低，扣分越多（每门课最多扣 10 分）
            penalty += (1.0 - worst_preference) * 10.0

        # 课程分布奖励
        distribution_bonus = self._calculate_distribution_bonus(daily_courses)

        # 计算最终得分，限幅在 0-100
        # 先把基础分+奖励限幅到 100，再扣惩罚：
        # 否则奖励会先吸收惩罚，使 avoid_* 类配置在高分区间看不出区别。
        final_score = min(100.0, base_score + distribution_bonus) - penalty

        return max(0.0, min(100.0, final_score))

    def _calculate_distribution_bonus(self, daily_courses: Dict[int, List]) -> float:
        """计算课程分布奖励

        奖励标准：
        1. 课程分布越均匀，奖励越高（最高10分）
        2. 避免某天课程过多（超过6门课程开始扣分）
        3. 鼓励适度的课程密度（每天2-4门课程最佳）
        """
        if not daily_courses:
            return 0.0

        total_courses = sum(len(courses) for courses in daily_courses.values())
        if total_courses == 0:
            return 0.0

        # 计算每天课程数量
        daily_counts = [len(courses) for courses in daily_courses.values()]

        # 1. 分布均匀性奖励（基于方差，方差越小越均匀）
        if len(daily_counts) > 1:
            mean_count = sum(daily_counts) / len(daily_counts)
            variance = sum((count - mean_count) ** 2 for count in daily_counts) / len(
                daily_counts
            )
            # 方差越小，奖励越高（最高5分）
            uniformity_bonus = max(0, 5.0 - variance)
        else:
            uniformity_bonus = 5.0  # 只有一天有课程，给满分

        # 2. 课程密度奖励
        density_bonus = 0.0
        for count in daily_counts:
            if 2 <= count <= 4:
                density_bonus += 2.0  # 每天2-4门课程，每天奖励2分
            elif count == 1:
                density_bonus += 1.0  # 每天1门课程，每天奖励1分
            elif count == 5:
                density_bonus += 1.0  # 每天5门课程，每天奖励1分
            elif count >= 6:
                density_bonus -= (count - 5) * 1.0  # 超过5门课程开始扣分

        return min(10.0, uniformity_bonus + density_bonus)

    def _calculate_time_preference_score(
        self, selected_courses: List[SelectedCourse]
    ) -> float:
        """计算时间偏好分数"""
        if not selected_courses:
            return 0.0

        total_score = 0.0
        total_slots = 0

        for selected_course in selected_courses:
            for time_slot in selected_course.time_slots:
                preference_score = self.config.get_time_preference_score(
                    time_slot.start_section
                )
                total_score += preference_score
                total_slots += 1

        return (total_score / total_slots * 100) if total_slots > 0 else 0.0

    def _calculate_campus_consistency_score(
        self, selected_courses: List[SelectedCourse]
    ) -> float:
        """计算校区一致性分数"""
        if not selected_courses:
            return 100.0

        # 按天统计校区使用情况
        daily_campuses = defaultdict(set)

        for selected_course in selected_courses:
            for time_slot in selected_course.time_slots:
                daily_campuses[time_slot.weekday].add(
                    self.config.normalize_campus(selected_course.course.campus)
                )

        # 计算跨校区惩罚
        total_days = len(daily_campuses)
        cross_campus_days = sum(
            1 for campuses in daily_campuses.values() if len(campuses) > 1
        )

        if total_days == 0:
            return 100.0

        consistency_ratio = 1.0 - (cross_campus_days / total_days)
        return consistency_ratio * 100

    def _calculate_course_distribution_score(
        self, selected_courses: List[SelectedCourse]
    ) -> float:
        """计算课程分布均匀性分数"""
        if not selected_courses:
            return 100.0

        # 统计每天的课程节次数
        daily_sections = defaultdict(set)

        for selected_course in selected_courses:
            for time_slot in selected_course.time_slots:
                weekday = time_slot.weekday
                for section in range(
                    time_slot.start_section, time_slot.end_section + 1
                ):
                    daily_sections[weekday].add(section)

        if not daily_sections:
            return 100.0

        # 计算分布均匀性
        section_counts = [len(sections) for sections in daily_sections.values()]

        if len(section_counts) == 1:
            return 80.0  # 只有一天有课，分布不够均匀

        # 使用标准差衡量均匀性
        mean_sections = sum(section_counts) / len(section_counts)
        variance = sum((count - mean_sections) ** 2 for count in section_counts) / len(
            section_counts
        )
        std_dev = math.sqrt(variance)

        # 标准差越小，分布越均匀
        max_std_dev = mean_sections  # 最大可能的标准差
        if max_std_dev == 0:
            return 100.0

        uniformity_ratio = 1.0 - (std_dev / max_std_dev)
        return max(0.0, uniformity_ratio * 100)

    def _calculate_credit_efficiency_score(
        self, selected_courses: List[SelectedCourse]
    ) -> float:
        """计算学分效率分数"""
        if not selected_courses:
            return 0.0

        total_credits = sum(course.course.credits for course in selected_courses)
        total_hours = sum(course.course.hours for course in selected_courses)

        if total_hours == 0:
            return 0.0

        # 学分效率 = 学分数 / 学时数
        efficiency = total_credits / total_hours

        # 正常情况下，学分效率在0.5-1.0之间
        # 将其映射到0-100分
        normalized_efficiency = min(1.0, efficiency / 0.75)  # 0.75作为理想效率
        return normalized_efficiency * 100

    def rank_schedules(
        self, schedules: List["ScheduleResult"]
    ) -> List["ScheduleResult"]:
        """对排课方案进行排序"""

        # 按总分降序排序，硬约束满足的方案优先
        def sort_key(schedule):
            if schedule.score.hard_constraints_satisfied:
                return (1, schedule.score.total_score)  # 硬约束满足的方案
            else:
                return (0, schedule.score.total_score)  # 硬约束不满足的方案

        return sorted(schedules, key=sort_key, reverse=True)

    def get_schedule_comparison(
        self, schedule1: "ScheduleResult", schedule2: "ScheduleResult"
    ) -> Dict[str, str]:
        """比较两个排课方案"""
        comparison = {}

        # 总分比较
        if schedule1.score.total_score > schedule2.score.total_score:
            comparison["总分"] = (
                f"方案1更优 ({schedule1.score.total_score:.1f} vs {schedule2.score.total_score:.1f})"
            )
        elif schedule1.score.total_score < schedule2.score.total_score:
            comparison["总分"] = (
                f"方案2更优 ({schedule2.score.total_score:.1f} vs {schedule1.score.total_score:.1f})"
            )
        else:
            comparison["总分"] = f"相同 ({schedule1.score.total_score:.1f})"

        # 各项分数比较
        score_items = [
            ("时间偏好", "time_preference_score"),
            ("校区一致性", "campus_consistency_score"),
            ("课程分布", "course_distribution_score"),
            ("学分效率", "credit_efficiency_score"),
        ]

        for name, attr in score_items:
            score1 = getattr(schedule1.score, attr)
            score2 = getattr(schedule2.score, attr)

            if score1 > score2:
                comparison[name] = f"方案1更优 ({score1:.1f} vs {score2:.1f})"
            elif score1 < score2:
                comparison[name] = f"方案2更优 ({score2:.1f} vs {score1:.1f})"
            else:
                comparison[name] = f"相同 ({score1:.1f})"

        # 约束满足比较
        if (
            schedule1.score.hard_constraints_satisfied
            and not schedule2.score.hard_constraints_satisfied
        ):
            comparison["硬约束"] = "方案1满足，方案2不满足"
        elif (
            not schedule1.score.hard_constraints_satisfied
            and schedule2.score.hard_constraints_satisfied
        ):
            comparison["硬约束"] = "方案2满足，方案1不满足"
        elif (
            schedule1.score.hard_constraints_satisfied
            and schedule2.score.hard_constraints_satisfied
        ):
            comparison["硬约束"] = "都满足"
        else:
            comparison["硬约束"] = "都不满足"

        return comparison

    def get_improvement_suggestions(self, schedule: "ScheduleResult") -> List[str]:
        """获取改进建议"""
        suggestions = []

        # 基于评分给出建议
        if schedule.score.time_preference_score < 70:
            suggestions.append("建议调整课程时间，避免早课和晚课")

        if schedule.score.campus_consistency_score < 80:
            suggestions.append("建议减少跨校区安排，提高校区一致性")

        if schedule.score.course_distribution_score < 70:
            suggestions.append("建议调整课程分布，使每天的课程数更加均匀")

        if schedule.score.credit_efficiency_score < 60:
            suggestions.append("建议选择学分效率更高的课程")

        # 基于冲突给出建议
        if schedule.conflicts:
            conflict_types = set(c.conflict_type for c in schedule.conflicts)
            if "time" in conflict_types:
                suggestions.append("存在时间冲突，需要调整课程时间安排")
            if "campus" in conflict_types:
                suggestions.append("存在校区冲突，建议选择同一校区的课程")
            if "credit" in conflict_types:
                suggestions.append("学分不满足要求，需要调整课程选择")

        if not suggestions:
            suggestions.append("当前方案已经很好，无需特别调整")

        return suggestions
