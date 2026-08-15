#!/usr/bin/env python3
"""排课引擎

核心排课算法：三阶段策略 + 回溯搜索。

历史说明（战略项已收收尾）：
本文件曾同时包含两套求解器——一套基于 OR-Tools CP-SAT
（``_build_model`` / ``_add_*_constraints`` / ``_set_objective`` /
``_solve_model`` / ``SolutionCollector``），一套自定义回溯算法。
但 CP-SAT 那套：

* **没有任何调用方**（GitNexus 确认 ``_build_model`` / ``_solve_model``
  无入边、不属于任何执行流）；
* 实现本身不完整：时间约束的主循环体是 ``pass``（占用表永远为空），
  校区约束与每日上限也是 ``pass``，学分约束还引用了不存在的
  ``config.enforce_credit_requirements``；
* 与回溯路径重复定义了同一批约束语义，两边容易逐渐不一致。

因此已删除 CP-SAT 残代码，只保留真正生效的回溯实现：
``generate_schedules()`` → ``_schedule_timed_courses()`` →
``_constraint_satisfaction_scheduling()`` → ``_backtrack_scheduling()``。
如将来确定要改用 CP-SAT，应在约束语义和特征测试稳定后重写，
而不是继续养一份不可达的半成品。
"""

import time
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

from ..logging_config import get_logger
from ..models import SelectedCourse, TimeSlot
from ..credit_manager import CreditManager
from .config import SchedulingConfig
from .constraints import ConstraintChecker
from .models import ScheduleResult, ScheduleStatus
from .evaluator import ScheduleEvaluator

logger = get_logger(__name__)


class SchedulingEngine:
    """排课引擎"""

    # 回溯阶段至少搜集这么多个候选解，再按评分选最优。
    # 取 8 是在“能跳出首个贪心解”和“不把求解时间拖长”之间取平衡；
    # 搜索仍受 max_solve_time_seconds 截止，不会因此无限变慢。
    # ponytail: 定值候选池，若大规模课表下最优性不够再改自适应。
    CANDIDATE_POOL_SIZE = 8

    def __init__(self, config: SchedulingConfig, credit_manager: CreditManager):
        self.config = config
        self.credit_manager = credit_manager
        self.constraint_checker = ConstraintChecker(config, credit_manager)
        self.evaluator = ScheduleEvaluator(config)
        self._timed_out = False

    def generate_schedules(
        self,
        available_courses: List[SelectedCourse],
        max_solutions: Optional[int] = None,
    ) -> List[ScheduleResult]:
        """生成排课方案（三阶段处理）"""
        start_time = time.time()

        if max_solutions is None:
            max_solutions = self.config.max_solutions

        # 🔧 P0 修复：超时标记，供回溯算法回写并影响最终结果状态
        self._timed_out = False

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
        logger.debug("CreditManager状态检查：")
        for category, requirement in self.credit_manager.requirements.items():
            logger.debug(
                f"  {category}: {requirement.completed_credits:.1f}/{requirement.required_credits:.1f} (已完成: {requirement.is_completed})"
            )

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

            # 🔧 P0 修复：超时且无任何可行解时，返回一个显式 TIMEOUT 结果，
            # 而不是空列表——否则服务层只能报“未找到方案”，
            # 用户无法区分“真的无解”和“时间不够”。
            if not results and self._timed_out:
                timeout_result = ScheduleResult(
                    schedule_id="timeout",
                    status=ScheduleStatus.TIMEOUT,
                    selected_courses=[],
                    solve_time_seconds=time.time() - start_time,
                    total_courses_considered=len(available_courses),
                )
                timeout_result.add_warning(
                    f"求解已达时间上限（{self.config.max_solve_time_seconds} 秒）且未找到可行方案，"
                    "请尝试延长时间限制、放宽约束模式或减少待排课程。"
                )
                print(
                    f"⚠️ 求解超时且无可行解，耗时 {time.time() - start_time:.2f} 秒"
                )
                return [timeout_result]

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
            logger.debug("🔍 [调试] 开始恢复CreditManager状态...")
            for category, original_credits in original_completed.items():
                if category in self.credit_manager.requirements:
                    current_credits = self.credit_manager.requirements[
                        category
                    ].completed_credits
                    if current_credits != original_credits:
                        logger.debug(
                            f"🔍 [调试] 恢复 {category}: {current_credits:.1f} -> {original_credits:.1f}"
                        )
                        self.credit_manager.requirements[
                            category
                        ].completed_credits = original_credits
                    else:
                        logger.debug(
                            f"✅ [调试] {category}: 状态未变化 ({current_credits:.1f})"
                        )
            logger.debug("🔍 [调试] CreditManager状态恢复完成")

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
                    # 🔧 P2 修复：统一使用 _time_slot_keys() 生成键。
                    # 之前这里写入 (week, weekday, section)，
                    # 而 _has_time_conflict/_add_course_time_slots 用
                    # (weekday, section, week)，两套不兼容的键序。
                    self._add_course_time_slots(
                        final_selected_course, time_slots_used
                    )

        return [selected_courses] if selected_courses else [[]]

    def _constraint_satisfaction_scheduling(
        self, timed_courses: List[SelectedCourse], max_solutions: int
    ) -> List[List[SelectedCourse]]:
        """完整的约束满足排课算法"""
        print(f"开始约束满足排课：{len(timed_courses)} 门有时间课程")

        # 第1步：候选减量——只在确实过多时介入。
        # 阈值跟 CANDIDATE_LIMIT 保持一致：之前写死 15，而真实培养方案
        # 单学期待选就有 18 门，每次都会被预筛，反而丢掉回溯需要的课。
        if len(timed_courses) > self.CANDIDATE_LIMIT:
            print(f"课程数量较多({len(timed_courses)}门)，进行候选减量...")
            timed_courses = self._intelligent_course_filtering(timed_courses)
            print(f"减量完成：保留 {len(timed_courses)} 门候选课程")

        # 第2步：按课程编码分组，实现同一课程不同班次互斥
        course_groups = self._group_courses_by_code_from_selected(timed_courses)
        print(f"课程分组完成：{len(course_groups)} 个课程组")

        # 第3步：计算学分需求
        credit_requirements = self._calculate_credit_requirements()

        # 第4步：使用回溯算法生成满足约束的方案
        # 🔧 P0 修复：为活跃回溯路径设置时间上限
        solutions = []
        deadline = None
        if self.config.max_solve_time_seconds and self.config.max_solve_time_seconds > 0:
            deadline = time.monotonic() + self.config.max_solve_time_seconds
            print(f"求解时间上限：{self.config.max_solve_time_seconds} 秒")

        # 回溯产出的先后取决于启发式，不等于评分顺序。对常见的小规模
        # 单学期输入（<=12 个课程组）完整枚举截止时间内的全部候选，确保
        # 返回的第一项真的是该搜索空间内最高评分方案。更大输入继续使用
        # 有界候选池，避免指数搜索拖垮交互。
        search_limit = (
            float("inf")
            if len(course_groups) <= 12
            else max(max_solutions, self.CANDIDATE_POOL_SIZE)
        )

        self._backtrack_scheduling(
            course_groups=course_groups,
            credit_requirements=credit_requirements,
            current_solution=[],
            used_time_slots=set(),
            solutions=solutions,
            max_solutions=search_limit,
            deadline=deadline,
        )

        if self._timed_out:
            print(
                f"⚠️ 求解超时（{self.config.max_solve_time_seconds} 秒），返回已找到的 {len(solutions)} 个方案"
            )

        solutions = self._rank_solutions(solutions, max_solutions)

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

    def _rank_solutions(
        self,
        solutions: List[List[SelectedCourse]],
        max_solutions: int,
    ) -> List[List[SelectedCourse]]:
        """去重并按评分降序，只保留前 max_solutions 个。

        回溯会反复产出同一组课程（不同搜索路径、相同结果），
        且产出顺序是搜索顺序而非质量顺序。前端只展示第一个方案，
        所以必须在这里定序，否则用户拿到的是首个可行解而非最优解。
        """
        if not solutions:
            return []

        unique: Dict[Tuple, List[SelectedCourse]] = {}
        for solution in solutions:
            # 课程编码+班次能唯一确定一个方案
            key = tuple(sorted((sc.course.code, sc.class_num) for sc in solution))
            if key not in unique:
                unique[key] = solution

        def sort_key(solution: List[SelectedCourse]) -> Tuple[float, float, int]:
            score = self.evaluator.evaluate_schedule(
                solution, self.credit_manager, self.config
            )
            total_credits = sum(sc.course.credits for sc in solution)
            # 评分相同时偏好学分多、课程多的方案
            return (score.total_score, total_credits, len(solution))

        ranked = sorted(unique.values(), key=sort_key, reverse=True)
        return ranked[:max_solutions]

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
        deadline: Optional[float] = None,
    ):
        """回溯算法进行排课

        deadline: time.monotonic() 绝对截止时间。超时后停止深入搜索，
        保留已找到的解（对应 config.max_solve_time_seconds）。
        """

        # 🔧 P0 修复：落实时间限制。max_solve_time_seconds 之前只在
        # 不可达的 CP-SAT 求解路径中使用，活跃回溯路径无任何上限。
        if deadline is not None and time.monotonic() >= deadline:
            self._timed_out = True
            return

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

            # 🔧 P0 修复：达到上限后立即停止，避免超出 max_solutions。
            # 之前只在函数入口和递归返回后检查，四个 append 点之间会溢出。
            if len(solutions) >= max_solutions:
                return

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
                and len(solutions) < max_solutions
            ):
                # 🔧 增加调试信息：显示保存的解的详细内容
                course_codes = [sc.course.code for sc in current_solution]
                total_credits = sum(sc.course.credits for sc in current_solution)
                solutions.append(current_solution.copy())
                logger.debug(
                    f"   💾 保存终端部分解：{len(current_solution)}门课程，总学分{total_credits:.1f}"
                )
                logger.debug(f"       课程列表: {course_codes}")
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
                and len(solutions) < max_solutions
            ):
                # 🔧 增加调试信息：显示启发式保存的解的详细内容
                course_codes = [sc.course.code for sc in current_solution]
                total_credits = sum(sc.course.credits for sc in current_solution)
                solutions.append(current_solution.copy())
                logger.debug(
                    f"   💾 保存启发式部分解：{len(current_solution)}门课程，总学分{total_credits:.1f}"
                )
                logger.debug(f"       课程列表: {course_codes}")
            return

        # 尝试该课程组的每个班次
        for candidate_course in course_groups[next_course_code]:
            # 检查是否与当前解冲突
            if self._is_course_compatible(
                candidate_course, current_solution, used_time_slots
            ):
                # 🔧 关键修复：检查学分效率约束
                # category_pool 传整个候选集（所有课程组展平），而不是只传
                # 本组的班次——“救场”需要知道同类别里有没有其它课程
                # 可选，而同类别的课程分属不同的课程组（课程编码不同）。
                if self._should_add_course_for_credit_efficiency(
                    candidate_course,
                    current_solution,
                    credit_requirements,
                    category_pool=[
                        course
                        for group in course_groups.values()
                        for course in group
                    ],
                ):
                    # 添加到当前解
                    current_solution.append(candidate_course)
                    new_used_slots = used_time_slots.copy()
                    self._add_course_time_slots(candidate_course, new_used_slots)

                    # 递归搜索
                    logger.debug(
                        f"       🔄 递归搜索：添加 {candidate_course.course.code}，当前解包含 {len(current_solution)} 门课程"
                    )
                    self._backtrack_scheduling(
                        course_groups,
                        credit_requirements,
                        current_solution,
                        new_used_slots,
                        solutions,
                        max_solutions,
                        deadline,
                    )

                    # 🔧 修复：在回溯前检查当前解是否应该被保存
                    if (
                        current_solution
                        and len(current_solution) >= 6
                        and self.config.credit_constraint_mode.value == "optimal"
                        and len(solutions) < max_solutions
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
                                logger.debug(
                                    f"       💾 保存回溯前解：{len(current_solution)}门课程，总学分{total_credits:.1f}"
                                )
                                logger.debug(f"           课程列表: {course_codes}")

                    # 回溯
                    logger.debug(
                        f"       ⬅️ 回溯：移除 {candidate_course.course.code}，回到 {len(current_solution) - 1} 门课程"
                    )
                    current_solution.pop()

                    # 如果已找到足够的解，提前退出
                    if len(solutions) >= max_solutions:
                        return

                    # 超时后也要提前退出，避免继续尝试其他班次
                    if deadline is not None and time.monotonic() >= deadline:
                        self._timed_out = True
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
                deadline,
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
        return any(
            key in used_time_slots for key in self._time_slot_keys(candidate_course)
        )

    def _is_campus_compatible(
        self, candidate_course: SelectedCourse, current_solution: List[SelectedCourse]
    ) -> bool:
        """检查校区兼容性"""
        from .config import CampusConflictMode

        if self.config.campus_conflict_mode == CampusConflictMode.DISABLED:
            return True

        candidate_campus = self.config.normalize_campus(candidate_course.course.campus)

        for existing_course in current_solution:
            existing_campus = self.config.normalize_campus(existing_course.course.campus)

            # 如果校区相同，无冲突
            if candidate_campus == existing_campus:
                continue

            # 检查是否在同一天有课
            if self._courses_on_same_day(candidate_course, existing_course):
                if self.config.campus_conflict_mode == CampusConflictMode.DAILY:
                    # 日内模式：同一天不允许跨校区
                    return False
                elif self.config.campus_conflict_mode == CampusConflictMode.PERIOD:
                    # 时段模式：按配置的最小转场节次判断，而不是固定时段分组。
                    # ConstraintChecker 使用相同的语义，确保“搜索是否接纳”与
                    # “结果是否判冲突”不会互相矛盾。
                    # 时段模式：同一半天时段内不得跨校区，跳块（隔着午休/
                    # 晚饭）则允许。ConstraintChecker 使用相同语义，确保“搜索是否
                    # 接纳”与“结果是否判冲突”不会互相矛盾。
                    if not self._is_campus_transfer_feasible(
                        candidate_course, existing_course
                    ):
                        return False

        return True

    def _is_campus_transfer_feasible(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """两门跨校区课之间能不能完成转场。

        仅同一天且周次重叠时需要转场。判据是两节课是否落在同一个
        半天时段（config.half_day_blocks）：同块意味着中间只有课间操，
        赶不上；跳块意味着隔着午休或晚饭，赶得上。
        """
        for ts1 in course1.time_slots:
            for ts2 in course2.time_slots:
                if ts1.weekday != ts2.weekday:
                    continue
                if not (set(ts1.weeks) & set(ts2.weeks)):
                    continue

                blocks1 = self.config.blocks_for_range(ts1.start_section, ts1.end_section)
                blocks2 = self.config.blocks_for_range(ts2.start_section, ts2.end_section)
                if blocks1 & blocks2:
                    return False
        return True

    def _courses_on_same_day(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程是否在同一天有课"""
        weekdays1 = set(ts.weekday for ts in course1.time_slots)
        weekdays2 = set(ts.weekday for ts in course2.time_slots)
        return bool(weekdays1 & weekdays2)

    @staticmethod
    def _time_slot_keys(course: SelectedCourse):
        """生成课程占用的时间段键

        🔧 P2 修复：以前三处分别手写 (weekday, section, week) 和
        (week, weekday, section) 两种键序，写入和读取对不上，
        使部分时间冲突检测静默失效。现在只从这一处生成。
        键序约定：(weekday, section, week)。
        """
        for time_slot in course.time_slots:
            for week in time_slot.weeks:
                for section in range(
                    time_slot.start_section, time_slot.end_section + 1
                ):
                    yield (time_slot.weekday, section, week)

    def _add_course_time_slots(
        self, course: SelectedCourse, used_time_slots: Set[Tuple]
    ):
        """将课程的时间段添加到已使用时间段集合"""
        used_time_slots.update(self._time_slot_keys(course))

    #: 预筛选保留的候选课上限。它只是回溯的规模闸，不是最终选择。
    #: 取 24（> 真实单学期待选量），使典型培养方案不会被预筛削掉。
    CANDIDATE_LIMIT = 24

    def _intelligent_course_filtering(
        self, timed_courses: List[SelectedCourse]
    ) -> List[SelectedCourse]:
        """限制候选规模，供回溯搜索使用。

        注意它的职责边界：**只做减量，不做选择**。

        之前这里跑一遗贪心（同类内小学分优先 + 学分效率拦）并把结果
        当成候选集，等于提前替回溯做了决定——而贪心在这里并不最优。
        实测：核心课要 11 分，池里 [2,2,2.5,3,3,3]。贪心从小到大拿到
        2+2+2.5+3=9.5，再加任一 3.0 就超上限（12.0）被拒 → 卡在 9.5；
        而回溯自己能拿到 3+3+3+2 = 11.0 达标。预筛把那些 3.0 分的课
        提前丢了，回溯根本看不到它们。

        现在只做两件事：
        1. 同一课程编码的多个班次只留冲突最少的一个（真正的去重）
        2. 若仍超 CANDIDATE_LIMIT，按类别轮流裁到上限（保证每类都有代表）

        选哪些课交给回溯 + _rank_solutions。
        """
        print("执行候选课程减量...")

        # 第1步：按课程编码分组，每组只保留一个最优班次
        course_groups = self._group_courses_by_code_from_selected(timed_courses)
        candidate_courses = []

        for course_code, courses in course_groups.items():
            # 为每个课程组选择最优班次（时间冲突最少的）
            best_course = self._select_best_class_from_group(courses, timed_courses)
            candidate_courses.append(best_course)

        print(
            f"第1步完成：同课程多班次去重，{len(timed_courses)} 门 → {len(candidate_courses)} 门"
        )

        if len(candidate_courses) <= self.CANDIDATE_LIMIT:
            return candidate_courses

        # 第2步：仍过多时按类别轮流裁到上限。
        # 用 _sort_courses_by_priority 的轮流序，保证截断时各类都有代表；
        # 不在这里做学分效率判定（那是回溯的责任）。
        trimmed = self._sort_courses_by_priority(candidate_courses)[: self.CANDIDATE_LIMIT]
        print(f"第2步完成：超出上限，按类别轮流裁到 {len(trimmed)} 门")
        return trimmed

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
        """排序候选课：各类别轮流（round-robin），同类别内优先低学分。

        之前按 ``gap * 10`` 平铺排序，结果缺口最大的类别会把队列头部
        全包下。配上 ``_intelligent_course_filtering`` 的 15 门上限，
        小缺口类别根本轮不到：真实培养方案（18 门）下，核心课（缺 11 分）
        占满名额，公共必修（缺 4 分）与限制性选修（缺 1 分）被整类丢弃。
        公共必修是必须上的课，丢掉直接导致方案不可用。

        现在改为按类别分组后交错输出，使任何截断位置都能覆盖到全部
        有缺口的类别；类别之间的先后仍按缺口降序。
        """
        credit_requirements = self._calculate_credit_requirements()

        def category_rank(category: str) -> float:
            """类别优先度：已修满 < 无缺口 < 按缺口降序。"""
            requirement = self.credit_manager.get_requirement(category)
            if requirement and requirement.is_completed:
                return -1000.0
            gap = credit_requirements.get(category, 0)
            if gap <= 0:
                return -100.0
            return gap

        def within_category_key(course: SelectedCourse) -> float:
            # 同类别内低学分优先，减少不必要的学分溢出
            credits = course.course.credits
            return credits if credits > 0 else float("inf")

        grouped: Dict[str, List[SelectedCourse]] = defaultdict(list)
        for course in courses:
            grouped[course.custom_category].append(course)
        for bucket in grouped.values():
            bucket.sort(key=within_category_key)

        ordered_categories = sorted(
            grouped.keys(), key=lambda category: category_rank(category), reverse=True
        )

        # 轮流取课：每轮从每个类别各取一门
        result: List[SelectedCourse] = []
        round_index = 0
        while True:
            appended = False
            for category in ordered_categories:
                bucket = grouped[category]
                if round_index < len(bucket):
                    result.append(bucket[round_index])
                    appended = True
            if not appended:
                break
            round_index += 1

        return result

    def _should_add_course_for_credit_efficiency(
        self,
        candidate: SelectedCourse,
        selected_courses: List[SelectedCourse],
        credit_requirements: Dict[str, float],
        category_pool: Optional[List[SelectedCourse]] = None,
    ) -> bool:
        """检查是否应该添加该课程（学分效率约束）

        category_pool：整个候选池（可选）。只用于“救场”判定：
        只有当同类别里找不到不超上限的替代课时，才允许突破上限。
        不传则退化为“只要该类为空就救”（偏宽松）。
        """
        category = candidate.custom_category

        logger.debug(f"🔍 检查课程 {candidate.course.code} (类别: {category})")

        # 获取该类别的学分要求信息
        requirement = self.credit_manager.get_requirement(category)
        if not requirement:
            # 如果类别不存在于学分管理器中，不允许添加
            logger.debug(
                f"   ❌ 学分效率约束：未知类别 {category}，拒绝 {candidate.course.code}"
            )
            return False

        logger.debug(
            f"   📊 类别状态：{requirement.completed_credits:.1f}/{requirement.required_credits:.1f} (已完成: {requirement.is_completed})"
        )

        # 检查该类别是否已经修满
        if requirement.is_completed:
            logger.debug(
                f"   ❌ 学分效率约束：{category} 已修满({requirement.completed_credits:.1f}/{requirement.required_credits:.1f})，拒绝 {candidate.course.code}"
            )
            return False

        # 如果该类别没有学分缺口，不允许添加
        if category not in credit_requirements:
            logger.debug(
                f"   ❌ 学分效率约束：{category} 无学分缺口，拒绝 {candidate.course.code}"
            )
            return False

        # credit_requirements[category] 已经是“还差多少学分”的缺口（required - completed）
        # 因此这里只能累加本次新选的学分，不能再加 completed_credits（否则重复扣减）
        required_gap = credit_requirements[category]

        # 计算该类别本次已选的新增学分
        selected_gap_credits = 0.0
        selected_in_category = []
        for sc in selected_courses:
            if sc.custom_category == category:
                selected_gap_credits += sc.course.credits
                selected_in_category.append(sc.course.code)

        # 调试信息：显示当前已选课程
        if selected_in_category:
            logger.debug(
                f"   📋 当前已选{category}课程: {selected_in_category} (新增学分: {selected_gap_credits:.1f}/缺口 {required_gap:.1f})"
            )
        else:
            logger.debug(
                f"   📋 当前未选择{category}课程 (已修学分: {requirement.completed_credits:.1f}，缺口: {required_gap:.1f})"
            )

        # 如果已经填满缺口，不再添加更多课程
        if selected_gap_credits >= required_gap:
            logger.debug(
                f"   ❌ 学分效率约束：{category} 已满足要求(新增 {selected_gap_credits:.1f}/缺口 {required_gap:.1f})，跳过 {candidate.course.code}"
            )
            return False

        # 如果未满足要求，检查添加后是否会过度超出。
        # 溢出上限用固定学分（max_credit_overflow）而不是比例：
        # 比例制在小缺口上张不开——限选要求 1.0、ratio=0.2 时上限 1.2，
        # 连一门 1.5 分的课都收不下，而培养方案只规定下限、无上限。
        new_total = selected_gap_credits + candidate.course.credits
        overflow_allowance = (
            self.config.max_credit_overflow if self.config.allow_credit_overflow else 0.0
        )
        overflow_limit = required_gap + overflow_allowance

        # 浮点容差，避免 0.1+0.2 类误差误报
        if new_total > overflow_limit + 1e-9:
            # 救场：该类别一门都没选中，而且同类里没有不超上限的替代课时，
            # 允许突破上限收下这一门。用户把课放进候选池就是明确想修；
            # 若该类唯一可选课超上限，拒掉会使该类 0 学分——
            # 比溢出 0.5 分更不合培养方案。
            #
            # 必须先确认“没有更小的选择”，否则会被滥用：
            # 要求 2.0、池里有 [1.0, 3.0] 时，回溯会先试空集状态，
            # 救场直接放过 3.0，反而把正常的 1.0 挤掉。
            if self.config.rescue_empty_category and selected_gap_credits <= 0:
                has_smaller_option = False
                if category_pool:
                    for other in category_pool:
                        if other is candidate:
                            continue
                        if other.custom_category != category:
                            continue
                        if other.course.credits <= overflow_limit + 1e-9:
                            has_smaller_option = True
                            break
                if not has_smaller_option:
                    logger.debug(
                        f"   ⚠️ 救场：{category} 尚无选中课程且无替代，"
                        f"允许 {candidate.course.code}({candidate.course.credits}学分) "
                        f"突破溢出上限 {overflow_limit:.1f}"
                    )
                    return True
            logger.debug(
                f"   ❌ 学分效率约束：添加 {candidate.course.code}({candidate.course.credits}学分) 会导致 {category} 过度超出({new_total:.1f} > 上限 {overflow_limit:.1f})"
            )
            return False

        logger.debug(f"   ✅ 允许添加 {candidate.course.code}")
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
                # 🔧 P2 修复：使用与 _add_course_time_slots 一致的键序
                # (weekday, section, week)，之前这里用的是 (week, weekday, section)，
                # 导致冲突检测永远未命中。
                conflict = False
                for week in weeks:
                    for section in range(start_section, end_section + 1):
                        if (weekday, section, week) in used_slots:
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

        # 🔧 P0 修复：求解超时时标记状态，使上层可以区分“完整搜索完成”与“超时截断”
        if getattr(self, "_timed_out", False):
            if result.status == ScheduleStatus.SUCCESS:
                result.status = ScheduleStatus.TIMEOUT
            result.add_warning(
                f"求解已达时间上限（{self.config.max_solve_time_seconds} 秒），结果可能不是最优解"
            )

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
