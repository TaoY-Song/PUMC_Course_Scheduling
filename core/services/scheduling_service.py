"""
排课服务实现 - 封装排课算法的服务层

这个模块实现了ISchedulingService接口，作为UI和排课算法之间的桥梁。
"""

import time
from typing import List, Optional
from threading import Lock

from .interfaces import ISchedulingService, SchedulingStatus, ServiceEvent
from ..models import SelectedCourse
from ..scheduling.config import SchedulingConfig
from ..scheduling.engine import SchedulingEngine
from ..scheduling.models import ScheduleResult
from ..credit_manager import CreditManager


class SchedulingService(ISchedulingService):
    """排课服务实现类"""

    def __init__(self, event_manager=None, credit_manager=None):
        """初始化排课服务"""
        self._config: Optional[SchedulingConfig] = None
        self._status: SchedulingStatus = SchedulingStatus.IDLE
        self._engine: Optional[SchedulingEngine] = None
        self._credit_manager: CreditManager = credit_manager or CreditManager()
        self._lock = Lock()
        self._event_manager = event_manager

        # 初始化默认配置
        self._config = SchedulingConfig()
        self._engine = SchedulingEngine(self._config, self._credit_manager)

    def configure(self, config: SchedulingConfig) -> None:
        """配置排课参数"""
        with self._lock:
            self._config = config
            self._engine = SchedulingEngine(config, self._credit_manager)
            self._status = SchedulingStatus.CONFIGURING

            # 发送配置变化事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="config_changed",
                    data={"config": config},
                    timestamp=time.time(),
                    source="scheduling_service",
                )
                self._event_manager.emit(event)

            self._status = SchedulingStatus.IDLE

    def execute(self, courses: List[SelectedCourse]) -> ScheduleResult:
        """执行排课算法"""
        with self._lock:
            if self._status == SchedulingStatus.RUNNING:
                raise RuntimeError(f"服务当前状态为 {self._status.value}，无法执行排课")
            
            self._status = SchedulingStatus.IDLE

            if not self._engine:
                raise RuntimeError("排课引擎未初始化")

            self._status = SchedulingStatus.RUNNING

            try:
                # 发送开始事件
                if self._event_manager:
                    event = ServiceEvent(
                        event_type="scheduling_started",
                        data={"course_count": len(courses)},
                        timestamp=time.time(),
                        source="scheduling_service",
                    )
                    self._event_manager.emit(event)

                # 执行排课算法
                results = self._engine.generate_schedules(courses, max_solutions=1)

                if results:
                    result = results[0]
                    self._status = SchedulingStatus.COMPLETED

                    # 发送完成事件
                    if self._event_manager:
                        event = ServiceEvent(
                            event_type="scheduling_completed",
                            data={
                                "result": result,
                                "selected_count": len(result.selected_courses),
                                "total_score": result.score.total_score,
                            },
                            timestamp=time.time(),
                            source="scheduling_service",
                        )
                        self._event_manager.emit(event)

                    return result
                else:
                    self._status = SchedulingStatus.FAILED
                    # 分析具体失败原因
                    failure_analysis = self._analyze_scheduling_failure(courses)

                    # 发送失败事件
                    if self._event_manager:
                        event = ServiceEvent(
                            event_type="scheduling_failed",
                            data={"error": failure_analysis},
                            timestamp=time.time(),
                            source="scheduling_service",
                        )
                        self._event_manager.emit(event)

                    return None

            except ImportError as e:
                # OR-Tools导入错误，发送特殊事件
                self._status = SchedulingStatus.FAILED
                if self._event_manager:
                    event = ServiceEvent(
                        event_type="ortools_missing",
                        data={"error": str(e)},
                        timestamp=time.time(),
                        source="scheduling_service",
                    )
                    self._event_manager.emit(event)
                return None
            except Exception as e:
                self._status = SchedulingStatus.FAILED

                # 发送失败事件
                if self._event_manager:
                    event = ServiceEvent(
                        event_type="scheduling_failed",
                        data={"error": str(e)},
                        timestamp=time.time(),
                        source="scheduling_service",
                    )
                    self._event_manager.emit(event)

                # 不再重新抛出异常，避免UI层重复处理
                # 返回None表示失败，UI层通过事件机制处理
                return None

    def _analyze_scheduling_failure(self, courses: List[SelectedCourse]) -> str:
        """分析排课失败的具体原因"""
        try:
            if not self._engine or not self._config:
                return "排课引擎或配置未初始化"

            analysis = ["🔍 排课失败原因分析："]

            # 1. 基本信息
            analysis.append(f"📊 课程总数：{len(courses)}门")

            # 2. 检查约束模式设置
            analysis.append("⚙️  当前约束配置：")
            analysis.append(
                f"   • 学分约束模式：{self._config.credit_constraint_mode.value}"
            )
            analysis.append(
                f"   • 校区冲突模式：{self._config.campus_conflict_mode.value}"
            )

            # 3. 分析时间冲突
            time_conflicts = self._analyze_time_conflicts(courses)
            if time_conflicts > 0:
                analysis.append(f"⏰ 时间冲突：发现{time_conflicts}对课程存在时间冲突")
                if time_conflicts > len(courses) * 0.5:
                    analysis.append("   ❌ 时间冲突过多，这是主要失败原因")

            # 4. 分析学分要求
            credit_analysis = self._analyze_credit_constraints(courses)
            if credit_analysis:
                analysis.extend(credit_analysis)

            # 5. 分析校区冲突
            if self._config.campus_conflict_mode.value != "DISABLED":
                campus_analysis = self._analyze_campus_conflicts(courses)
                if campus_analysis:
                    analysis.extend(campus_analysis)

            # 6. 提供解决建议
            analysis.append("")
            analysis.append("💡 解决建议：")

            if self._config.credit_constraint_mode.value == "REQUIRED":
                analysis.append("   • 尝试切换到'优化模式'以降低学分约束严格度")

            if time_conflicts > len(courses) * 0.3:
                analysis.append("   • 检查课程时间安排，移除冲突严重的课程")

            if self._config.campus_conflict_mode.value != "DISABLED":
                analysis.append("   • 考虑禁用校区冲突约束或调整为'时段模式'")

            analysis.append("   • 检查已修学分设置是否合理")

            return "\n".join(analysis)

        except Exception as e:
            return f"排课失败，且无法分析具体原因：{str(e)}"

    def _analyze_time_conflicts(self, courses: List[SelectedCourse]) -> int:
        """分析时间冲突"""
        conflicts = 0
        for i, course1 in enumerate(courses):
            for j, course2 in enumerate(courses[i + 1 :], i + 1):
                if self._courses_have_time_conflict(course1, course2):
                    conflicts += 1
        return conflicts

    def _courses_have_time_conflict(
        self, course1: SelectedCourse, course2: SelectedCourse
    ) -> bool:
        """检查两门课程是否有时间冲突"""
        return SelectedCourse.has_time_conflict(course1, course2)

    def _analyze_credit_constraints(self, courses: List[SelectedCourse]) -> List[str]:
        """分析学分约束问题"""
        analysis = []

        if not self._engine or not hasattr(self._engine, "credit_manager"):
            return analysis

        credit_manager = self._engine.credit_manager

        # 计算各类别可选学分
        category_credits = {}
        for course in courses:
            category = course.custom_category
            if category not in category_credits:
                category_credits[category] = 0
            category_credits[category] += course.course.credits

        # 检查学分要求
        unsatisfied_categories = []
        total_required = 0
        total_available = 0

        for category, requirement in credit_manager.requirements.items():
            remaining = requirement.remaining_credits
            available = category_credits.get(category, 0)

            total_required += remaining
            total_available += available

            if remaining > 0:
                if available < remaining:
                    unsatisfied_categories.append(
                        f"   • {category}: 需要{remaining}学分，仅有{available}学分可选"
                    )
                elif available == 0:
                    unsatisfied_categories.append(
                        f"   • {category}: 需要{remaining}学分，但没有该类别的课程"
                    )

        # 🔧 修复：只在必需模式下报告学分约束问题
        if (
            unsatisfied_categories
            and self._config.credit_constraint_mode.value == "required"
        ):
            analysis.append("📋 学分约束问题：")
            analysis.extend(unsatisfied_categories)
            analysis.append("   ❌ '必需模式'要求严格满足所有类别学分要求")

        # 🔧 修复：只在必需模式下报告总学分不足
        if (
            total_available < total_required
            and self._config.credit_constraint_mode.value == "required"
        ):
            analysis.append(
                f"📊 总学分不足：需要{total_required}学分，仅有{total_available}学分可选"
            )

        return analysis

    def _analyze_campus_conflicts(self, courses: List[SelectedCourse]) -> List[str]:
        """分析校区冲突问题"""
        analysis = []

        if self._config.campus_conflict_mode.value == "disabled":
            return analysis  # 禁用模式不检查校区冲突

        # 按天分组检查校区
        daily_courses = {}
        for course in courses:
            for slot in course.time_slots:
                day = slot.weekday
                if day not in daily_courses:
                    daily_courses[day] = []
                daily_courses[day].append((course, slot))

        conflict_days = []
        for day, day_course_slots in daily_courses.items():
            if len(day_course_slots) <= 1:
                continue

            # 按时间排序
            day_course_slots.sort(key=lambda x: x[1].start_section)

            weekday_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            day_conflicts = []

            if self._config.campus_conflict_mode.value == "daily":
                # DAILY模式：检查同一天是否有不同校区
                campuses = set(course.course.campus for course, _ in day_course_slots)
                if len(campuses) > 1:
                    day_conflicts.append(
                        f"   • {weekday_names[day]}: {', '.join(campuses)}"
                    )

            elif self._config.campus_conflict_mode.value == "period":
                # PERIOD模式：检查同时段内是否跨校区
                periods = [
                    (1, 4, "时段1(1-4节)"),
                    (5, 8, "时段2(5-8节)"),
                    (9, 10, "时段3(9-10节)"),
                ]

                for period_start, period_end, period_name in periods:
                    period_courses = []

                    # 收集该时段内的课程
                    for course, slot in day_course_slots:
                        if (
                            slot.start_section <= period_end
                            and slot.end_section >= period_start
                        ):
                            period_courses.append((course, slot))

                    # 检查同时段内的校区一致性（考虑周次重叠）
                    if len(period_courses) > 1:
                        # 检查每对课程是否有周次重叠且校区不同
                        for i in range(len(period_courses)):
                            for j in range(i + 1, len(period_courses)):
                                course1, slot1 = period_courses[i]
                                course2, slot2 = period_courses[j]

                                # 检查周次是否有重叠
                                weeks1_set = set(slot1.weeks)
                                weeks2_set = set(slot2.weeks)
                                weeks_overlap = weeks1_set & weeks2_set

                                # 只有在周次重叠且校区不同时才报告冲突
                                if (
                                    weeks_overlap
                                    and course1.course.campus != course2.course.campus
                                ):
                                    overlap_weeks = sorted(list(weeks_overlap))
                                    weeks_str = (
                                        f"{overlap_weeks[0]}-{overlap_weeks[-1]}周"
                                        if len(overlap_weeks) > 1
                                        else f"{overlap_weeks[0]}周"
                                    )
                                    day_conflicts.append(
                                        f"   • {weekday_names[day]} {period_name}: {course1.course.campus} -> {course2.course.campus} ({weeks_str}内必须同校区)"
                                    )

            conflict_days.extend(day_conflicts)

        if conflict_days:
            analysis.append("🏫 校区冲突问题：")
            analysis.extend(conflict_days)

            # 根据不同模式显示正确的约束描述
            if self._config.campus_conflict_mode.value == "daily":
                analysis.append("   ❌ 'daily'模式不允许同一天跨校区")
            elif self._config.campus_conflict_mode.value == "period":
                analysis.append(
                    "   ❌ 'period'模式要求同时段内必须同校区（时段1:1-4节，时段2:5-8节，时段3:9-10节）"
                )

        return analysis

    def get_status(self) -> SchedulingStatus:
        """获取当前状态"""
        return self._status

    def cancel(self) -> bool:
        """取消执行"""
        with self._lock:
            if self._status == SchedulingStatus.RUNNING:
                self._status = SchedulingStatus.CANCELLED

                # 发送取消事件
                if self._event_manager:
                    event = ServiceEvent(
                        event_type="scheduling_cancelled",
                        data={},
                        timestamp=time.time(),
                        source="scheduling_service",
                    )
                    self._event_manager.emit(event)

                return True
            return False

    def get_config(self) -> SchedulingConfig:
        """获取当前配置"""
        return self._config

    def reset(self) -> None:
        """重置服务状态"""
        with self._lock:
            self._status = SchedulingStatus.IDLE
