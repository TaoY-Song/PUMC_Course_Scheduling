#!/usr/bin/env python3
"""
排课引擎
基于OR-Tools CP-SAT求解器的核心排课算法实现
"""

import time
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

try:
    from ortools.sat.python import cp_model

    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("警告: OR-Tools未安装，排课功能将不可用")

from ..models import Course, SelectedCourse, TimeSlot
from ..credit_manager import CreditManager
from .config import SchedulingConfig
from .constraints import ConstraintChecker
from .models import ScheduleResult, ScheduleStatus
from .evaluator import ScheduleEvaluator


class SchedulingEngine:
    """排课引擎"""

    def __init__(self, config: SchedulingConfig, credit_manager: CreditManager):
        self.config = config
        self.credit_manager = credit_manager
        self.constraint_checker = ConstraintChecker(config, credit_manager)
        self.evaluator = ScheduleEvaluator(config)

        if not ORTOOLS_AVAILABLE:
            raise ImportError(
                "OR-Tools未安装，无法使用排课功能。\n"
                "请运行以下命令安装OR-Tools：\n"
                "pip install ortools\n"
                "或者：\n"
                "conda install -c conda-forge ortools"
            )

    def generate_schedules(
        self,
        available_courses: List[SelectedCourse],
        max_solutions: Optional[int] = None,
    ) -> List[ScheduleResult]:
        """生成排课方案（三阶段处理）"""
        start_time = time.time()

        if max_solutions is None:
            max_solutions = self.config.max_solutions

        print(f"开始排课：{len(available_courses)} 门可选课程")
        print(
            f"🎯 当前模式：{self.config.credit_constraint_mode.value.upper()} ({'必需模式' if self.config.credit_constraint_mode.value == 'required' else '优化模式'})"
        )

        # 🔧 辅助修复：重置CreditManager的临时状态，确保多次运行时不会累积
        # 重置为用户手动设置的基础已修学分，保留用户在学分设置中的配置
        original_completed = {}
        for category, requirement in self.credit_manager.requirements.items():
            original_completed[category] = requirement.completed_credits
            # 重置为用户设置的基础已修学分，而不是0.0
            requirement.completed_credits = requirement.base_completed_credits

        # 调试：打印CreditManager状态
        print("🔍 CreditManager状态检查：")
        for category, requirement in self.credit_manager.requirements.items():
            print(
                f"  {category}: {requirement.completed_credits:.1f}/{requirement.required_credits:.1f} (已完成: {requirement.is_completed})"
            )
        print()

        try:
            # 阶段1：处理无时间线上课程
            online_courses, timed_courses = self._separate_courses(available_courses)
            selected_online_courses = self._process_online_courses(online_courses)
            print(f"阶段1完成：选择了 {len(selected_online_courses)} 门无时间线上课程")

            # 阶段2：核心排课（有时间安排的课程）
            if timed_courses:
                timed_solutions = self._schedule_timed_courses(
                    timed_courses, max_solutions
                )
                print(f"阶段2完成：生成了 {len(timed_solutions)} 个有时间课程方案")
            else:
                timed_solutions = [[]]  # 空的有时间课程方案

            # 阶段3：合并结果
            results = []
            for i, timed_solution in enumerate(timed_solutions):
                combined_solution = selected_online_courses + timed_solution
                result = self._create_schedule_result(
                    f"方案_{i + 1}",
                    combined_solution,
                    time.time() - start_time,
                    len(available_courses),
                )
                results.append(result)

            # 按分数排序
            results.sort(key=lambda x: x.score.total_score, reverse=True)

            print(
                f"排课完成：生成 {len(results)} 个完整方案，耗时 {time.time() - start_time:.2f} 秒"
            )
            return results

        except Exception as e:
            print(f"排课失败：{e}")
            import traceback

            traceback.print_exc()

            # 返回失败结果
            failed_result = ScheduleResult(
                schedule_id="failed",
                status=ScheduleStatus.FAILED,
                selected_courses=[],
                solve_time_seconds=time.time() - start_time,
                total_courses_considered=len(available_courses),
            )
            failed_result.add_warning(f"排课算法执行失败：{str(e)}")
            return [failed_result]
        finally:
            # 🔧 关键修复：恢复CreditManager的原始状态
            print("🔍 [调试] 开始恢复CreditManager状态...")
            for category, original_credits in original_completed.items():
                if category in self.credit_manager.requirements:
                    current_credits = self.credit_manager.requirements[
                        category
                    ].completed_credits
                    if current_credits != original_credits:
                        print(
                            f"🔍 [调试] 恢复 {category}: {current_credits:.1f} -> {original_credits:.1f}"
                        )
                        self.credit_manager.requirements[
                            category
                        ].completed_credits = original_credits
                    else:
                        print(
                            f"✅ [调试] {category}: 状态未变化 ({current_credits:.1f})"
                        )
            print("🔍 [调试] CreditManager状态恢复完成")

    def _separate_courses(
        self, courses: List[SelectedCourse]
    ) -> Tuple[List[SelectedCourse], List[SelectedCourse]]:
        """分离无时间线上课程和有时间安排的课程"""
        online_courses = []
        timed_courses = []

        for selected_course in courses:
            # 扩展的线上课程识别逻辑
            is_online = self._is_online_course(selected_course)

            if is_online:
                print(
                    f"🌐 识别为线上课程：{selected_course.course.code} - {selected_course.course.name}"
                )
                online_courses.append(selected_course)
            else:
                timed_courses.append(selected_course)

        print(
            f"📊 课程分离完成：线上课程 {len(online_courses)} 门，有时间课程 {len(timed_courses)} 门"
        )
        return online_courses, timed_courses

    def _is_online_course(self, selected_course: SelectedCourse) -> bool:
        """判断是否为线上课程"""
        # 1. 优先检查SelectedCourse对象的is_online属性
        if (
            hasattr(selected_course, "is_online")
            and selected_course.is_online is not None
        ):
            return selected_course.is_online

        course = selected_course.course

        # 2. 检查Course对象的is_online属性（新增）
        if hasattr(course, "is_online") and course.is_online is not None:
            return course.is_online

        # 3. 备用方案：基于课程名称的关键词识别
        online_name_keywords = [
            "线上",
            "网络",
            "在线",
            "远程",
            "网课",
            "慕课",
            "MOOC",
            "前沿技术",
            "研究进展",
            "学术前沿",  # 特定的线上课程模式
        ]

        for keyword in online_name_keywords:
            if keyword in course.name:
                return True

        # 4. 基于校区的识别
        online_campus_keywords = [
            "线上",
            "网络",
            "在线",
            "远程",
            "虚拟",
            "系统所",  # 苏州系统所的课程通常是线上的
        ]

        for keyword in online_campus_keywords:
            if keyword in course.campus:
                return True

        # 5. 基于课程编码模式识别（某些编码模式表示线上课程）
        if course.code.startswith("BIOL40"):  # 生物前沿类课程通常是线上的
            return True

        # 5. 基于时间安排识别：没有具体时间安排的课程可能是线上课程
        if not selected_course.time_slots or len(selected_course.time_slots) == 0:
            # 进一步检查是否是真正的线上课程
            if any(
                keyword in course.name for keyword in ["前沿", "进展", "研究", "学术"]
            ):
                return True

        return False

    def _process_online_courses(
        self, online_courses: List[SelectedCourse]
    ) -> List[SelectedCourse]:
        """处理无时间线上课程（阶段1）- 高优先级选择"""
        selected_online = []

        # 计算各类别学分缺口（修复：正确考虑已修学分）
        category_gaps = {}
        for category, requirement in self.credit_manager.requirements.items():
            # 使用remaining_credits属性，它已经考虑了已修学分
            category_gaps[category] = max(0, requirement.remaining_credits)

        print(f"📊 线上课程处理 - 学分缺口：{category_gaps}")

        # 按自定义类别分组线上课程
        online_by_category = defaultdict(list)
        for selected_course in online_courses:
            online_by_category[selected_course.custom_category].append(selected_course)

        print(
            f"📱 线上课程分布：{dict((k, len(v)) for k, v in online_by_category.items())}"
        )

        # 优先级排序：按学分缺口大小排序类别，优先处理缺口大的类别
        sorted_categories = sorted(
            category_gaps.items(), key=lambda x: x[1], reverse=True
        )

        for category, gap in sorted_categories:
            if gap > 0 and category in online_by_category:
                print(f"🎯 处理类别 {category}，缺口 {gap} 学分")

                # 线上课程高优先级：优先选择学分适中的课程（不是最小）
                available_courses = online_by_category[category]

                # 优先级排序：学分在1-3之间的课程优先，然后按学分升序
                def online_priority(sc):
                    credits = sc.course.credits
                    if 1 <= credits <= 3:
                        return (0, credits)  # 高优先级组
                    else:
                        return (1, credits)  # 低优先级组

                available_courses.sort(key=online_priority)

                current_gap = gap
                for candidate_course in available_courses:
                    if current_gap > 0:
                        print(
                            f"   ✅ 选择线上课程：{candidate_course.course.code} - {candidate_course.course.name} ({candidate_course.course.credits}学分)"
                        )
                        selected_online.append(candidate_course)
                        current_gap -= candidate_course.course.credits
                    else:
                        break

        print(f"🎉 线上课程选择完成：{len(selected_online)} 门课程")

        # 🔧 关键修复：更新CreditManager状态，将选择的线上课程学分添加到已修学分中
        # 这样阶段2在计算学分缺口时就会考虑阶段1已选择的课程，避免重复计算
        for selected_course in selected_online:
            category = selected_course.custom_category
            credits = selected_course.course.credits
            self.credit_manager.add_completed_credits(category, credits)
            print(f"   📊 更新学分状态：{category} +{credits:.1f}学分")

        return selected_online

    def _schedule_timed_courses(
        self, timed_courses: List[SelectedCourse], max_solutions: int
    ) -> List[List[SelectedCourse]]:
        """排课有时间安排的课程（阶段2）"""
        print("使用完整的约束满足排课算法")

        # 使用完整的约束满足算法
        try:
            return self._constraint_satisfaction_scheduling(
                timed_courses, max_solutions
            )
        except Exception as e:
            print(f"完整算法失败，回退到简化算法: {e}")
            return self._simple_schedule_timed_courses(timed_courses)

    def _simple_schedule_timed_courses(
        self, timed_courses: List[SelectedCourse]
    ) -> List[List[SelectedCourse]]:
        """简化的有时间课程排课（时间效率优先）"""
        selected_courses = []

        # 计算各类别学分缺口
        category_gaps = {}
        for category, requirement in self.credit_manager.requirements.items():
            category_gaps[category] = (
                requirement.required_credits - requirement.completed_credits
            )

        # 按自定义类别分组课程
        courses_by_category = defaultdict(list)
        for selected_course in timed_courses:
            courses_by_category[selected_course.custom_category].append(selected_course)

        # 时间效率优先策略：优先选择能快速满足学分要求的课程
        current_week = 1
        time_slots_used = set()  # 记录已使用的时间段

        # 按优先级排序类别（学分要求高的优先）
        sorted_categories = sorted(
            category_gaps.items(), key=lambda x: x[1], reverse=True
        )

        for category, gap in sorted_categories:
            if gap > 0 and category in courses_by_category:
                available_courses = courses_by_category[category]
                # 🔧 修正：使用最优学分匹配策略，而不是贪心选择最大学分
                selected_for_category = self._select_optimal_courses_for_category(
                    available_courses, gap, time_slots_used, current_week
                )

                # 添加选中的课程到结果中
                for final_selected_course in selected_for_category:
                    selected_courses.append(final_selected_course)
                    gap -= final_selected_course.course.credits

                    # 记录使用的时间段
                    for time_slot in final_selected_course.time_slots:
                        for week in time_slot.weeks:
                            for section in range(
                                time_slot.start_section, time_slot.end_section + 1
                            ):
                                time_slots_used.add((week, time_slot.weekday, section))

        return [selected_courses] if selected_courses else [[]]

    def _constraint_satisfaction_scheduling(
        self, timed_courses: List[SelectedCourse], max_solutions: int
    ) -> List[List[SelectedCourse]]:
        """完整的约束满足排课算法"""
        print(f"开始约束满足排课：{len(timed_courses)} 门有时间课程")

        # 第1步：预筛选 - 如果课程过多且冲突严重，先进行智能筛选
        if len(timed_courses) > 15:
            print(f"课程数量较多({len(timed_courses)}门)，进行智能预筛选...")
            timed_courses = self._intelligent_course_filtering(timed_courses)
            print(f"预筛选完成：保留 {len(timed_courses)} 门优质课程")

        # 第2步：按课程编码分组，实现同一课程不同班次互斥
        course_groups = self._group_courses_by_code_from_selected(timed_courses)
        print(f"课程分组完成：{len(course_groups)} 个课程组")

        # 第3步：计算学分需求
        credit_requirements = self._calculate_credit_requirements()

        # 第4步：使用回溯算法生成满足约束的方案
        solutions = []
        self._backtrack_scheduling(
            course_groups=course_groups,
            credit_requirements=credit_requirements,
            current_solution=[],
            used_time_slots=set(),
            solutions=solutions,
            max_solutions=max_solutions,
        )

        print(f"约束满足排课完成：生成 {len(solutions)} 个方案")

        # 如果没有找到解，提供详细的诊断信息
        if len(solutions) == 0:
            print("🔍 排课失败诊断：")
            print(f"  - 课程组数量: {len(course_groups)}")
            print(f"  - 学分要求: {credit_requirements}")
            print(f"  - 约束模式: {self.config.credit_constraint_mode.value}")
            print(f"  - 校区冲突模式: {self.config.campus_conflict_mode.value}")

            # 检查时间冲突
            conflict_count = self._analyze_time_conflicts(timed_courses)
            print(f"  - 时间冲突数量: {conflict_count}")

            # 检查学分分布
            self._analyze_credit_distribution(timed_courses, credit_requirements)

        return solutions

    def _group_courses_by_code_from_selected(
        self, selected_courses: List[SelectedCourse]
    ) -> Dict[str, List[SelectedCourse]]:
        """从SelectedCourse列表按课程编码分组"""
        groups = defaultdict(list)
        for selected_course in selected_courses:
            course_code = selected_course.course.code
            groups[course_code].append(selected_course)
        return dict(groups)

    def _calculate_credit_requirements(self) -> Dict[str, float]:
        """计算各类别的学分需求"""
        requirements = {}
        for category, requirement in self.credit_manager.requirements.items():
            gap = requirement.required_credits - requirement.completed_credits
            if gap > 0:
                requirements[category] = gap
        return requirements

    def _calculate_credit_satisfaction_rate(
        self,
        current_solution: List[SelectedCourse],
        credit_requirements: Dict[str, float],
    ) -> float:
        """计算当前解的学分满足度"""
        if not credit_requirements:
            return 1.0

        # 计算各类别已选学分
        selected_credits = defaultdict(float)
        for course in current_solution:
            category = course.custom_category
            selected_credits[category] += course.course.credits

        # 计算满足度
        total_required = sum(credit_requirements.values())
        total_satisfied = 0

        for category, required in credit_requirements.items():
            satisfied = min(selected_credits[category], required)
            total_satisfied += satisfied

        return total_satisfied / total_required if total_required > 0 else 1.0

    def _analyze_time_conflicts(self, courses: List[SelectedCourse]) -> int:
        """分析时间冲突数量"""
        conflicts = 0
        for i, course1 in enumerate(courses):
            for j, course2 in enumerate(courses[i + 1 :], i + 1):
                if self._courses_have_time_conflict(course1, course2):
                    conflicts += 1
                    print(
                        f"    时间冲突: {course1.course.code} vs {course2.course.code}"
                    )
        return conflicts

    def _courses_have_time_conflict(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程是否有时间冲突"""
        return SelectedCourse.has_time_conflict(course1, course2)

    def _analyze_credit_distribution(
        self, courses: List[SelectedCourse], credit_requirements: Dict[str, float]
    ):
        """分析学分分布"""
        print("  - 学分分布分析:")
        category_credits = defaultdict(float)
        for course in courses:
            category_credits[course.custom_category] += course.course.credits

        for category, required in credit_requirements.items():
            available = category_credits[category]
            print(f"    {category}: 需要{required}学分, 可选{available}学分")

    def _backtrack_scheduling(
        self,
        course_groups: Dict[str, List[SelectedCourse]],
        credit_requirements: Dict[str, float],
        current_solution: List[SelectedCourse],
        used_time_slots: Set[Tuple],
        solutions: List[List[SelectedCourse]],
        max_solutions: int,
    ):
        """回溯算法进行排课"""

        # 如果已找到足够的解，停止搜索
        if len(solutions) >= max_solutions:
            return

        # 检查当前解是否满足学分要求
        if self._is_credit_requirements_satisfied(
            current_solution, credit_requirements
        ):
            # 找到一个完整解
            solutions.append(current_solution.copy())
            # 🔧 修正：不要立即返回，继续搜索其他解决方案
            # return  # 注释掉这个return，让算法继续搜索

        # 🔧 修正：延迟保存部分解，避免过早保存影响搜索完整性
        # 注释掉中途保存部分解的逻辑，让算法完成完整搜索
        # if self.config.credit_constraint_mode.value == "optimal":
        #     # 优化模式：保存有意义的部分解
        #     if len(current_solution) >= min(6, len(course_groups) * 0.6):  # 降低门槛，至少6门课或60%的课程组
        #         credit_satisfaction = self._calculate_credit_satisfaction_rate(current_solution, credit_requirements)
        #         if credit_satisfaction >= 0.5:  # 降低门槛，满足50%以上的学分要求就保存
        #             solutions.append(current_solution.copy())
        #             print(f"   💾 保存部分解：{len(current_solution)}门课程，学分满足度{credit_satisfaction:.1%}")
        #             # 继续搜索其他解决方案，不返回
        # 必需模式：不保存部分解，只有满足所有要求的解才会在上面被保存

        # 选择下一个课程组进行尝试
        remaining_groups = [
            code
            for code in course_groups.keys()
            if not any(sc.course.code == code for sc in current_solution)
        ]

        if not remaining_groups:
            # 🔧 修正：没有更多课程可选时，只在优化模式下保存部分解
            if (
                current_solution
                and self.config.credit_constraint_mode.value == "optimal"
            ):
                # 🔧 增加调试信息：显示保存的解的详细内容
                course_codes = [sc.course.code for sc in current_solution]
                total_credits = sum(sc.course.credits for sc in current_solution)
                solutions.append(current_solution.copy())
                print(
                    f"   💾 保存终端部分解：{len(current_solution)}门课程，总学分{total_credits:.1f}"
                )
                print(f"       课程列表: {course_codes}")
            return

        # 使用启发式选择：优先选择学分缺口最大的类别的课程
        next_course_code = self._select_next_course_by_heuristic(
            remaining_groups, course_groups, current_solution, credit_requirements
        )

        if next_course_code is None:
            # 🔧 修正：无法选择下一个课程时，只在优化模式下保存部分解
            if (
                current_solution
                and self.config.credit_constraint_mode.value == "optimal"
            ):
                # 🔧 增加调试信息：显示启发式保存的解的详细内容
                course_codes = [sc.course.code for sc in current_solution]
                total_credits = sum(sc.course.credits for sc in current_solution)
                solutions.append(current_solution.copy())
                print(
                    f"   💾 保存启发式部分解：{len(current_solution)}门课程，总学分{total_credits:.1f}"
                )
                print(f"       课程列表: {course_codes}")
            return

        # 尝试该课程组的每个班次
        for candidate_course in course_groups[next_course_code]:
            # 检查是否与当前解冲突
            if self._is_course_compatible(
                candidate_course, current_solution, used_time_slots
            ):
                # 🔧 关键修复：检查学分效率约束
                if self._should_add_course_for_credit_efficiency(
                    candidate_course, current_solution, credit_requirements
                ):
                    # 添加到当前解
                    current_solution.append(candidate_course)
                    new_used_slots = used_time_slots.copy()
                    self._add_course_time_slots(candidate_course, new_used_slots)

                    # 递归搜索
                    print(
                        f"       🔄 递归搜索：添加 {candidate_course.course.code}，当前解包含 {len(current_solution)} 门课程"
                    )
                    self._backtrack_scheduling(
                        course_groups,
                        credit_requirements,
                        current_solution,
                        new_used_slots,
                        solutions,
                        max_solutions,
                    )

                    # 🔧 修复：在回溯前检查当前解是否应该被保存
                    if (
                        current_solution
                        and len(current_solution) >= 6
                        and self.config.credit_constraint_mode.value == "optimal"
                    ):
                        credit_satisfaction = self._calculate_credit_satisfaction_rate(
                            current_solution, credit_requirements
                        )
                        if credit_satisfaction >= 0.5:  # 与终端部分解相同的标准
                            # 检查是否已经保存过相同的解
                            current_codes = set(
                                sc.course.code for sc in current_solution
                            )
                            is_duplicate = any(
                                set(sc.course.code for sc in existing_solution)
                                == current_codes
                                for existing_solution in solutions
                            )
                            if not is_duplicate:
                                course_codes = [
                                    sc.course.code for sc in current_solution
                                ]
                                total_credits = sum(
                                    sc.course.credits for sc in current_solution
                                )
                                solutions.append(current_solution.copy())
                                print(
                                    f"       💾 保存回溯前解：{len(current_solution)}门课程，总学分{total_credits:.1f}"
                                )
                                print(f"           课程列表: {course_codes}")

                    # 回溯
                    print(
                        f"       ⬅️ 回溯：移除 {candidate_course.course.code}，回到 {len(current_solution) - 1} 门课程"
                    )
                    current_solution.pop()

                    # 如果已找到足够的解，提前退出
                    if len(solutions) >= max_solutions:
                        return

        # 🔧 关键修复：无论当前课程组是否添加成功，都要继续尝试其他课程组
        # 这样即使某些课程被学分约束拒绝，也能继续搜索其他可行的课程组合
        remaining_groups_copy = [
            code
            for code in course_groups.keys()
            if code != next_course_code
            and not any(sc.course.code == code for sc in current_solution)
        ]

        if remaining_groups_copy:
            # 创建不包含当前课程组的新字典，继续递归搜索
            new_course_groups = {
                k: v for k, v in course_groups.items() if k != next_course_code
            }
            self._backtrack_scheduling(
                new_course_groups,
                credit_requirements,
                current_solution,
                used_time_slots,
                solutions,
                max_solutions,
            )

    def _is_credit_requirements_satisfied(
        self,
        current_solution: List[SelectedCourse],
        credit_requirements: Dict[str, float],
    ) -> bool:
        """检查当前解是否满足学分要求"""
        current_credits = defaultdict(float)
        for sc in current_solution:
            current_credits[sc.custom_category] += sc.course.credits

        # 计算总体满足度
        satisfied_categories = 0
        total_categories = len(credit_requirements)

        for category, required in credit_requirements.items():
            if current_credits[category] >= required:
                satisfied_categories += 1

        # 根据配置模式决定满足度要求
        if self.config.credit_constraint_mode.value == "required":
            # 🔧 必需模式：严格要求满足所有类别，一个都不能少（硬约束）
            return satisfied_categories == total_categories
        else:
            # 优化模式：满足大部分类别即可（软约束）
            return (
                satisfied_categories >= total_categories * 0.8 or total_categories == 0
            )

    def _select_next_course_by_heuristic(
        self,
        remaining_groups: List[str],
        course_groups: Dict[str, List[SelectedCourse]],
        current_solution: List[SelectedCourse],
        credit_requirements: Dict[str, float],
    ) -> Optional[str]:
        """使用启发式选择下一个要尝试的课程"""

        # 计算当前各类别学分
        current_credits = defaultdict(float)
        for sc in current_solution:
            current_credits[sc.custom_category] += sc.course.credits

        # 计算各类别的学分缺口
        category_gaps = {}
        for category, required in credit_requirements.items():
            gap = required - current_credits[category]
            if gap > 0:
                category_gaps[category] = gap

        if not category_gaps:
            return None  # 所有学分要求已满足

        # 选择学分缺口最大的类别的课程
        max_gap_category = max(category_gaps.keys(), key=lambda c: category_gaps[c])

        # 在剩余课程中找到属于该类别的课程
        for course_code in remaining_groups:
            courses_in_group = course_groups[course_code]
            if (
                courses_in_group
                and courses_in_group[0].custom_category == max_gap_category
            ):
                return course_code

        # 如果没找到，返回第一个剩余课程
        return remaining_groups[0] if remaining_groups else None

    def _is_course_compatible(
        self,
        candidate_course: SelectedCourse,
        current_solution: List[SelectedCourse],
        used_time_slots: Set[Tuple],
    ) -> bool:
        """检查候选课程是否与当前解兼容"""

        # 1. 检查同一课程不同班次互斥约束
        for existing_course in current_solution:
            if existing_course.course.code == candidate_course.course.code:
                return False  # 同一课程的其他班次已被选择

        # 2. 检查时间冲突
        if self._has_time_conflict(candidate_course, used_time_slots):
            return False

        # 3. 检查校区冲突（如果启用）
        if not self._is_campus_compatible(candidate_course, current_solution):
            return False

        return True

    def _has_time_conflict(
        self, candidate_course: SelectedCourse, used_time_slots: Set[Tuple]
    ) -> bool:
        """检查时间冲突"""
        for time_slot in candidate_course.time_slots:
            for week in time_slot.weeks:
                for section in range(
                    time_slot.start_section, time_slot.end_section + 1
                ):
                    time_key = (time_slot.weekday, section, week)
                    if time_key in used_time_slots:
                        return True
        return False

    def _is_campus_compatible(
        self, candidate_course: SelectedCourse, current_solution: List[SelectedCourse]
    ) -> bool:
        """检查校区兼容性"""
        from .config import CampusConflictMode

        if self.config.campus_conflict_mode == CampusConflictMode.DISABLED:
            return True

        candidate_campus = candidate_course.course.campus

        for existing_course in current_solution:
            existing_campus = existing_course.course.campus

            # 如果校区相同，无冲突
            if candidate_campus == existing_campus:
                continue

            # 检查是否在同一天有课
            if self._courses_on_same_day(candidate_course, existing_course):
                if self.config.campus_conflict_mode == CampusConflictMode.DAILY:
                    # 日内模式：同一天不允许跨校区
                    return False
                elif self.config.campus_conflict_mode == CampusConflictMode.PERIOD:
                    # 时段模式：检查是否在同一时段内
                    if self._courses_in_same_period(candidate_course, existing_course):
                        return False

        return True

    def _courses_in_same_period(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程是否在同一时段内（考虑周次重叠）"""
        # 定义时段
        periods = [
            (1, 4),  # 时段1：第1-4节
            (5, 8),  # 时段2：第5-8节
            (9, 10),  # 时段3：第9-10节
        ]

        for slot1 in course1.time_slots:
            for slot2 in course2.time_slots:
                # 只检查同一天的课程
                if slot1.weekday != slot2.weekday:
                    continue

                # 检查是否在同一时段内
                for period_start, period_end in periods:
                    # 检查两个时间段是否都与当前时段有重叠
                    slot1_in_period = (
                        slot1.start_section <= period_end
                        and slot1.end_section >= period_start
                    )
                    slot2_in_period = (
                        slot2.start_section <= period_end
                        and slot2.end_section >= period_start
                    )

                    if slot1_in_period and slot2_in_period:
                        # 进一步检查周次是否有重叠
                        weeks1_set = set(slot1.weeks)
                        weeks2_set = set(slot2.weeks)
                        weeks_overlap = weeks1_set & weeks2_set

                        # 只有在周次重叠时才认为在同一时段内
                        if weeks_overlap:
                            return True

        return False

    def _has_sufficient_campus_transfer_time(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程间是否有足够的校区转换时间"""
        min_gap = self.config.min_campus_transfer_time

        for ts1 in course1.time_slots:
            for ts2 in course2.time_slots:
                if ts1.weekday == ts2.weekday:
                    # 检查周次是否重叠
                    weeks1 = set(ts1.weeks)
                    weeks2 = set(ts2.weeks)
                    if weeks1 & weeks2:  # 有重叠周次
                        # 计算时间间隔
                        gap1 = abs(ts1.start_section - ts2.end_section - 1)
                        gap2 = abs(ts2.start_section - ts1.end_section - 1)
                        min_actual_gap = min(gap1, gap2)

                        if min_actual_gap < min_gap:
                            return False
        return True

    def _courses_on_same_day(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程是否在同一天有课"""
        weekdays1 = set(ts.weekday for ts in course1.time_slots)
        weekdays2 = set(ts.weekday for ts in course2.time_slots)
        return bool(weekdays1 & weekdays2)

    def _calculate_time_gap(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> int:
        """计算两门课程之间的最小时间间隔"""
        min_gap = float("inf")

        for ts1 in course1.time_slots:
            for ts2 in course2.time_slots:
                if ts1.weekday == ts2.weekday:
                    # 计算时间间隔
                    if ts1.end_section < ts2.start_section:
                        gap = ts2.start_section - ts1.end_section
                    elif ts2.end_section < ts1.start_section:
                        gap = ts1.start_section - ts2.end_section
                    else:
                        gap = 0  # 时间重叠

                    min_gap = min(min_gap, gap)

        return int(min_gap) if min_gap != float("inf") else 0

    def _add_course_time_slots(
        self, course: SelectedCourse, used_time_slots: Set[Tuple]
    ):
        """将课程的时间段添加到已使用时间段集合"""
        for time_slot in course.time_slots:
            for week in time_slot.weeks:
                for section in range(
                    time_slot.start_section, time_slot.end_section + 1
                ):
                    time_key = (time_slot.weekday, section, week)
                    used_time_slots.add(time_key)

    def _intelligent_course_filtering(
        self, timed_courses: List[SelectedCourse]
    ) -> List[SelectedCourse]:
        """智能课程筛选：从大量冲突课程中选择最优子集"""
        print("执行智能课程筛选算法...")

        # 第1步：按课程编码分组，每组只保留一个最优班次
        course_groups = self._group_courses_by_code_from_selected(timed_courses)
        candidate_courses = []

        for course_code, courses in course_groups.items():
            # 为每个课程组选择最优班次（时间冲突最少的）
            best_course = self._select_best_class_from_group(courses, timed_courses)
            candidate_courses.append(best_course)

        print(
            f"第1步完成：从{len(timed_courses)}门课程筛选到{len(candidate_courses)}门候选课程"
        )

        # 第2步：使用贪心算法选择无冲突的课程子集
        selected_courses = []
        used_time_slots = set()

        # 获取学分要求
        credit_requirements = self._calculate_credit_requirements()

        # 按学分需求优先级排序候选课程
        sorted_candidates = self._sort_courses_by_priority(candidate_courses)

        for candidate in sorted_candidates:
            # 检查是否与已选课程冲突
            if self._is_course_compatible(candidate, selected_courses, used_time_slots):
                # 检查学分效率约束：是否该类别已经满足要求
                if self._should_add_course_for_credit_efficiency(
                    candidate, selected_courses, credit_requirements
                ):
                    selected_courses.append(candidate)
                    self._add_course_time_slots(candidate, used_time_slots)

                    # 如果已经选择了足够的课程，可以停止
                    if len(selected_courses) >= 15:  # 限制最多15门课程
                        break

        print(f"第2步完成：最终筛选出{len(selected_courses)}门无冲突课程")
        return selected_courses

    def _select_best_class_from_group(
        self, courses: List[SelectedCourse], all_courses: List[SelectedCourse]
    ) -> SelectedCourse:
        """从同一课程的多个班次中选择最优的一个"""
        if len(courses) == 1:
            return courses[0]

        # 计算每个班次与其他所有课程的冲突数
        best_course = courses[0]
        min_conflicts = float("inf")

        for candidate in courses:
            conflicts = 0
            # 计算与其他课程的时间冲突数
            for other_course in all_courses:
                if other_course.course.code != candidate.course.code:
                    if self._has_time_conflict_between_courses(candidate, other_course):
                        conflicts += 1

            if conflicts < min_conflicts:
                min_conflicts = conflicts
                best_course = candidate

        return best_course

    def _has_time_conflict_between_courses(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程是否有时间冲突"""
        return SelectedCourse.has_time_conflict(course1, course2)

    def _sort_courses_by_priority(
        self, courses: List[SelectedCourse]
    ) -> List[SelectedCourse]:
        """按优先级排序课程：学分需求缺口大的类别优先，同类别内优先选择低学分课程"""
        credit_requirements = self._calculate_credit_requirements()

        def get_priority_score(course: SelectedCourse) -> float:
            category = course.custom_category

            # 检查该类别是否已修满
            requirement = self.credit_manager.get_requirement(category)
            if requirement and requirement.is_completed:
                # 已修满的类别优先级最低
                return -1000.0

            # 该类别的学分缺口越大，优先级越高
            gap = credit_requirements.get(category, 0)
            if gap <= 0:
                # 没有学分缺口的类别优先级很低
                return -100.0

            # 课程学分越低，优先级越高（避免不必要的超出）
            credits = course.course.credits
            # 使用倒数来让低学分课程有更高优先级
            credit_efficiency = 1.0 / credits if credits > 0 else 0
            return gap * 10 + credit_efficiency

        return sorted(courses, key=get_priority_score, reverse=True)

    def _should_add_course_for_credit_efficiency(
        self,
        candidate: SelectedCourse,
        selected_courses: List[SelectedCourse],
        credit_requirements: Dict[str, float],
    ) -> bool:
        """检查是否应该添加该课程（学分效率约束）"""
        category = candidate.custom_category

        print(f"🔍 检查课程 {candidate.course.code} (类别: {category})")

        # 获取该类别的学分要求信息
        requirement = self.credit_manager.get_requirement(category)
        if not requirement:
            # 如果类别不存在于学分管理器中，不允许添加
            print(
                f"   ❌ 学分效率约束：未知类别 {category}，拒绝 {candidate.course.code}"
            )
            return False

        print(
            f"   📊 类别状态：{requirement.completed_credits:.1f}/{requirement.required_credits:.1f} (已完成: {requirement.is_completed})"
        )

        # 检查该类别是否已经修满
        if requirement.is_completed:
            print(
                f"   ❌ 学分效率约束：{category} 已修满({requirement.completed_credits:.1f}/{requirement.required_credits:.1f})，拒绝 {candidate.course.code}"
            )
            return False

        # 如果该类别没有学分缺口，不允许添加
        if category not in credit_requirements:
            print(
                f"   ❌ 学分效率约束：{category} 无学分缺口，拒绝 {candidate.course.code}"
            )
            return False

        required_credits = credit_requirements[category]

        # 计算该类别当前已选的学分（包括已修学分）
        current_credits = 0
        selected_in_category = []
        for sc in selected_courses:
            if sc.custom_category == category:
                current_credits += sc.course.credits
                selected_in_category.append(sc.course.code)

        # 加上已修学分
        current_credits += requirement.completed_credits

        # 调试信息：显示当前已选课程
        if selected_in_category:
            print(
                f"   📋 当前已选{category}课程: {selected_in_category} (总学分: {current_credits:.1f})"
            )
        else:
            print(
                f"   📋 当前未选择{category}课程 (已修学分: {requirement.completed_credits:.1f})"
            )

        # 如果已经满足要求，不再添加更多课程
        if current_credits >= required_credits:
            print(
                f"   ❌ 学分效率约束：{category} 已满足要求({current_credits:.1f}/{required_credits:.1f})，跳过 {candidate.course.code}"
            )
            return False

        # 如果未满足要求，检查添加后是否会过度超出
        new_total = current_credits + candidate.course.credits
        if new_total > required_credits + 1:  # 允许最多1学分的必要超出
            print(
                f"   ❌ 学分效率约束：添加 {candidate.course.code}({candidate.course.credits}学分) 会导致 {category} 过度超出({new_total:.1f}/{required_credits:.1f})"
            )
            return False

        print(f"   ✅ 允许添加 {candidate.course.code}")
        return True

    def _allocate_time_slot(
        self, start_week: int, used_slots: set
    ) -> Optional[TimeSlot]:
        """分配时间段，避免冲突"""
        # 简化的时间分配策略
        for weekday in range(1, 6):  # 周一到周五
            for start_section in [
                3,
                7,
                1,
                9,
            ]:  # 优先选择3-4节、7-8节，然后1-2节、9-10节
                end_section = start_section + 1
                weeks = list(range(start_week, min(start_week + 8, 21)))  # 8周课程

                # 检查是否有冲突
                conflict = False
                for week in weeks:
                    for section in range(start_section, end_section + 1):
                        if (week, weekday, section) in used_slots:
                            conflict = True
                            break
                    if conflict:
                        break

                if not conflict:
                    return TimeSlot(
                        weekday=weekday,
                        start_section=start_section,
                        end_section=end_section,
                        weeks=weeks,
                    )

        return None  # 无法分配时间段

    def _group_courses_by_code(self, courses: List[Course]) -> Dict[str, List[Course]]:
        """按课程编码分组"""
        groups = defaultdict(list)
        for course in courses:
            groups[course.code].append(course)
        return dict(groups)

    def _build_model(self, course_groups: Dict[str, List[Course]]) -> Tuple:
        """构建OR-Tools模型"""
        model = cp_model.CpModel()

        # 决策变量：每个课程组选择哪个班次（-1表示不选）
        variables = {}
        course_mapping = {}  # 变量值到课程的映射

        for course_code, courses in course_groups.items():
            # 为每个课程组创建一个变量，值域为 [0, len(courses)]
            # 0 表示不选择该课程，1-n 表示选择第几个班次
            var = model.NewIntVar(0, len(courses), f"course_{course_code}")
            variables[course_code] = var

            # 建立映射关系
            course_mapping[course_code] = {
                i + 1: course for i, course in enumerate(courses)
            }

        # 添加约束
        self._add_constraints(model, variables, course_mapping)

        # 设置目标函数
        self._set_objective(model, variables, course_mapping)

        return model, variables, course_mapping

    def _add_constraints(self, model, variables: Dict, course_mapping: Dict):
        """添加约束条件"""

        # 1. 时间冲突约束
        self._add_time_conflict_constraints(model, variables, course_mapping)

        # 2. 校区冲突约束
        self._add_campus_conflict_constraints(model, variables, course_mapping)

        # 3. 学分约束
        self._add_credit_constraints(model, variables, course_mapping)

        # 4. 每日课程数限制
        self._add_daily_limit_constraints(model, variables, course_mapping)

    def _add_time_conflict_constraints(
        self, model, variables: Dict, course_mapping: Dict
    ):
        """添加时间冲突约束"""
        # 构建时间段占用表
        time_slots_usage = defaultdict(
            list
        )  # {(weekday, section, week): [(course_code, class_index), ...]}

        for course_code, class_mapping in course_mapping.items():
            for class_index, course in class_mapping.items():
                # 这里需要从课程数据中获取时间安排
                # 由于Course模型中没有时间信息，我们需要扩展或使用其他方式
                # 暂时跳过具体实现，使用占位符
                pass

        # 添加时间冲突约束
        for time_key, course_list in time_slots_usage.items():
            if len(course_list) > 1:
                # 同一时间段最多选择一门课程
                constraint_vars = []
                for course_code, class_index in course_list:
                    var = variables[course_code]
                    # 创建布尔变量表示是否选择了这个班次
                    bool_var = model.NewBoolVar(f"selected_{course_code}_{class_index}")
                    # 正确的约束写法
                    model.Add(var == class_index).OnlyEnforceIf(bool_var)
                    model.Add(var != class_index).OnlyEnforceIf(bool_var.Not())
                    constraint_vars.append(bool_var)

                # 最多选择一个
                model.Add(sum(constraint_vars) <= 1)

    def _add_campus_conflict_constraints(
        self, model, variables: Dict, course_mapping: Dict
    ):
        """添加校区冲突约束"""
        # 根据配置决定是否添加校区约束
        if self.config.campus_conflict_mode.value == "disabled":
            return

        # 实现校区冲突约束逻辑
        # 暂时跳过具体实现
        pass

    def _add_credit_constraints(self, model, variables: Dict, course_mapping: Dict):
        """添加学分约束"""
        if not self.config.enforce_credit_requirements:
            return

        # 按类别统计学分
        category_credits = defaultdict(
            list
        )  # {category: [(course_code, class_index, credits), ...]}

        for course_code, class_mapping in course_mapping.items():
            for class_index, course in class_mapping.items():
                category = course.category  # 使用原始类别，实际应用中可能需要映射
                credits = course.credits
                category_credits[category].append((course_code, class_index, credits))

        # 为每个类别添加学分约束
        for category, requirement in self.credit_manager.requirements.items():
            if category not in category_credits:
                continue

            # 计算该类别的总学分
            credit_vars = []
            for course_code, class_index, credits in category_credits[category]:
                var = variables[course_code]
                # 创建布尔变量
                bool_var = model.NewBoolVar(
                    f"credit_{category}_{course_code}_{class_index}"
                )
                # 正确的约束写法
                model.Add(var == class_index).OnlyEnforceIf(bool_var)
                model.Add(var != class_index).OnlyEnforceIf(bool_var.Not())

                # 学分贡献
                credit_contribution = model.NewIntVar(
                    0, int(credits * 10), f"credit_contrib_{course_code}"
                )
                model.Add(
                    credit_contribution == bool_var * int(credits * 10)
                )  # 乘以10避免浮点数
                credit_vars.append(credit_contribution)

            # 学分要求约束
            if credit_vars:
                total_credits = model.NewIntVar(
                    0,
                    sum(int(c[2] * 10) for c in category_credits[category]),
                    f"total_credits_{category}",
                )
                model.Add(total_credits == sum(credit_vars))

                # 最低学分要求
                min_credits = int(requirement.required_credits * 10)
                model.Add(total_credits >= min_credits)

                # 最高学分限制（如果不允许超出）
                if not self.config.allow_credit_overflow:
                    model.Add(total_credits <= min_credits)

    def _add_daily_limit_constraints(
        self, model, variables: Dict, course_mapping: Dict
    ):
        """添加每日课程数限制"""
        # 实现每日课程数限制
        # 暂时跳过具体实现
        pass

    def _set_objective(self, model, variables: Dict, course_mapping: Dict):
        """设置目标函数"""
        # 目标：最大化选择的课程数（简化版本）
        objective_vars = []

        for course_code, var in variables.items():
            # 创建布尔变量表示是否选择了该课程
            selected = model.NewBoolVar(f"selected_{course_code}")
            # 正确的约束写法
            model.Add(var > 0).OnlyEnforceIf(selected)
            model.Add(var == 0).OnlyEnforceIf(selected.Not())
            objective_vars.append(selected)

        # 最大化选择的课程数
        model.Maximize(sum(objective_vars))

    def _solve_model(
        self, model, variables: Dict, course_mapping: Dict, max_solutions: int
    ) -> List[List[SelectedCourse]]:
        """求解模型"""
        solver = cp_model.CpSolver()

        # 设置求解参数
        solver.parameters.max_time_in_seconds = self.config.max_solve_time_seconds
        solver.parameters.enumerate_all_solutions = True

        # 解收集器
        solution_collector = SolutionCollector(variables, course_mapping, max_solutions)

        # 求解
        status = solver.Solve(model, solution_collector)

        if status == cp_model.OPTIMAL:
            print("找到最优解")
        elif status == cp_model.FEASIBLE:
            print("找到可行解")
        elif status == cp_model.INFEASIBLE:
            print("无可行解")
            return []
        elif status == cp_model.MODEL_INVALID:
            print("模型无效")
            return []
        else:
            print("求解超时或其他错误")
            return []

        return solution_collector.solutions

    def _create_schedule_result(
        self,
        schedule_id: str,
        selected_courses: List[SelectedCourse],
        solve_time: float,
        total_courses: int,
    ) -> ScheduleResult:
        """创建排课结果"""
        result = ScheduleResult(
            schedule_id=schedule_id,
            status=ScheduleStatus.SUCCESS,
            selected_courses=selected_courses,
            solve_time_seconds=solve_time,
            total_courses_considered=total_courses,
        )

        # 检查约束（只检查有时间安排的课程）
        timed_courses = [sc for sc in selected_courses if sc.time_slots]
        hard_constraints_satisfied, conflicts = (
            self.constraint_checker.check_all_hard_constraints(timed_courses)
        )
        result.conflicts = conflicts

        if not hard_constraints_satisfied:
            result.status = ScheduleStatus.PARTIAL

        # 评估方案（传递配置参数）
        result.score = self.evaluator.evaluate_schedule(
            selected_courses, self.credit_manager, self.config
        )
        result.score.hard_constraints_satisfied = hard_constraints_satisfied

        return result

    def _select_optimal_courses_for_category(
        self,
        available_courses: List[SelectedCourse],
        gap: float,
        time_slots_used: set,
        current_week: int,
    ) -> List[SelectedCourse]:
        """为指定类别选择最优的课程组合，最小化学分超出"""
        if gap <= 0:
            return []

        print(f"   🎯 为类别选择最优课程组合，需要{gap}学分")

        # 生成所有可能的课程组合
        from itertools import combinations

        best_combination = []
        best_score = float("inf")  # 最小化超出学分

        # 尝试不同数量的课程组合（1到所有课程）
        for r in range(1, len(available_courses) + 1):
            for combination in combinations(available_courses, r):
                total_credits = sum(course.course.credits for course in combination)

                # 检查是否满足最低要求
                if total_credits >= gap:
                    # 计算超出分数（越小越好）
                    overflow = total_credits - gap

                    # 检查时间冲突
                    if self._check_combination_time_feasibility(
                        combination, time_slots_used, current_week
                    ):
                        # 评分：超出学分越少越好，课程数量越少越好
                        score = overflow * 10 + len(combination)  # 超出学分权重更高

                        if score < best_score:
                            best_score = score
                            best_combination = combination
                            print(
                                f"   ✅ 找到更优组合: {[c.course.code for c in combination]}, "
                                f"总学分{total_credits}, 超出{overflow}, 评分{score}"
                            )

        # 为选中的课程分配时间段
        result = []
        for candidate_course in best_combination:
            time_slot = self._allocate_time_slot(current_week, time_slots_used)
            if time_slot:
                final_selected_course = SelectedCourse(
                    course=candidate_course.course,
                    class_num=candidate_course.class_num,
                    time_slots=[time_slot],
                    is_online=candidate_course.is_online,
                    custom_category=candidate_course.custom_category,
                    category_locked=candidate_course.category_locked,
                )
                result.append(final_selected_course)

        if result:
            total_credits = sum(c.course.credits for c in result)
            print(
                f"   🎉 最终选择: {[c.course.code for c in result]}, 总学分{total_credits}"
            )

        return result

    def _check_combination_time_feasibility(
        self, combination: tuple, time_slots_used: set, current_week: int
    ) -> bool:
        """检查课程组合的时间可行性"""
        # 简化检查：假设可以为每门课程分配不同的时间段
        # 实际实现中可以更精确地检查时间冲突
        return len(combination) <= 5  # 假设最多可以安排5门课程


if ORTOOLS_AVAILABLE:

    class SolutionCollector(cp_model.CpSolverSolutionCallback):
        """解收集器"""

        def __init__(self, variables: Dict, course_mapping: Dict, max_solutions: int):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.variables = variables
            self.course_mapping = course_mapping
            self.max_solutions = max_solutions
            self.solutions = []

        def on_solution_callback(self):
            """找到解时的回调"""
            if len(self.solutions) >= self.max_solutions:
                self.StopSearch()
                return

            selected_courses = []

            for course_code, var in self.variables.items():
                value = self.Value(var)
                if value > 0:  # 选择了该课程
                    course = self.course_mapping[course_code][value]

                    # 创建SelectedCourse对象
                    # 注意：这里需要时间安排信息，暂时使用空列表
                    selected_course = SelectedCourse(
                        course=course,
                        class_num=course.class_num,
                        time_slots=[],  # 需要从课程数据中获取
                        is_online=False,
                        custom_category=course.category,
                        is_imported=False,  # 排课引擎生成的课程不是导入的
                    )
                    selected_courses.append(selected_course)

            self.solutions.append(selected_courses)
else:
    # 如果ortools不可用，创建一个占位符类
    class SolutionCollector:
        def __init__(self, *args, **kwargs):
            pass
