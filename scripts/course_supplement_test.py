#!/usr/bin/env python3
"""
课程补充测试脚本
自动尝试将课程一览表中缺失的课程添加到排课结果中
"""

import sys
import os
import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Course, SelectedCourse, TimeSlot
from core.data_loader import CourseDataLoader
from core.import_export import SelectedCourseImporter, SelectedCourseExporter
from core.scheduling.constraints import ConstraintChecker
from core.scheduling.config import SchedulingConfig, CampusConflictMode
from core.credit_manager import CreditManager


class CourseSupplementTester:
    """课程补充测试器"""

    def __init__(self):
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.course_list_file = os.path.join(PROJECT_ROOT, "课程一览表.xlsx")
        self.schedule_result_file = os.path.join(PROJECT_ROOT, "排课结果.xlsx")
        self.output_file = os.path.join(PROJECT_ROOT, "补充后排课结果.xlsx")

        # 初始化组件
        self.data_loader = CourseDataLoader()
        self.importer = SelectedCourseImporter()
        self.exporter = SelectedCourseExporter()

        # 配置约束检查器（使用时段模式）
        self.config = SchedulingConfig(campus_conflict_mode=CampusConflictMode.PERIOD)
        self.credit_manager = CreditManager()
        self.constraint_checker = ConstraintChecker(self.config, self.credit_manager)

        # 统计信息
        self.stats = {
            "total_courses_in_list": 0,
            "total_courses_in_schedule": 0,
            "missing_courses": 0,
            "missing_online_courses": 0,
            "missing_offline_courses": 0,
            "successfully_added": 0,
            "successfully_added_online": 0,
            "successfully_added_offline": 0,
            "failed_to_add": 0,
            "failed_online": 0,
            "failed_offline": 0,
            "time_conflicts": 0,
            "campus_conflicts": 0,
            "other_conflicts": 0,
        }

        self.added_courses = []
        self.failed_courses = []

    def load_course_list(self) -> List[Course]:
        """加载课程一览表"""
        print("📚 正在加载课程一览表...")

        try:
            # 直接读取Excel文件以获取时间信息
            import pandas as pd

            df = pd.read_excel(self.course_list_file)
            print(f"✓ 成功读取Excel文件，共 {len(df)} 条记录")
            print(f"✓ Excel列名: {list(df.columns)}")

            courses = []
            self.course_time_info = {}  # 存储课程时间信息
            self.course_online_info = {}  # 存储课程线上状态信息

            for index, row in df.iterrows():
                try:
                    # 创建基本课程对象
                    course = Course(
                        code=str(row["课程编码"]).strip(),
                        name=str(row["课程名称"]).strip(),
                        department=str(row["开课院系"]).strip(),
                        category=str(row["课程类别"]).strip(),
                        class_num=int(row["班次"]),
                        campus=str(row["校区"]).strip(),
                        teacher=str(row["任课教师"]).strip(),
                        credits=float(row["学分"]),
                        hours=float(row["学时"]),
                        description=str(row.get("选课说明", "")).strip(),
                    )

                    # 解析时间信息并存储
                    time_slots = self._parse_time_from_excel_row(row)
                    self.course_time_info[course.code] = time_slots

                    # 解析线上状态信息并存储
                    is_online_str = str(row.get("是否线上", "否")).strip()
                    is_online = is_online_str == "是"
                    self.course_online_info[course.code] = is_online
                    print(
                        f"   📱 课程 {course.code} 线上状态: {is_online_str} -> {is_online}"
                    )

                    courses.append(course)

                except Exception as e:
                    print(f"⚠️ 第 {index + 1} 行数据转换失败: {e}")

            self.stats["total_courses_in_list"] = len(courses)
            print(f"✅ 成功加载 {len(courses)} 门课程")
            return courses

        except Exception as e:
            print(f"❌ 加载课程一览表失败: {e}")
            return []

    def load_schedule_result(self, all_courses: List[Course]) -> List[SelectedCourse]:
        """加载排课结果"""
        print("📋 正在加载排课结果...")

        try:
            # 使用已加载的课程数据创建临时加载器
            temp_loader = CourseDataLoader()
            temp_loader.courses = all_courses  # 使用已加载的课程数据

            selected_courses, import_report = self.importer.import_from_excel(
                self.schedule_result_file, temp_loader
            )
            self.stats["total_courses_in_schedule"] = len(selected_courses)
            print(f"✅ 成功加载 {len(selected_courses)} 门已选课程")
            return selected_courses
        except Exception as e:
            print(f"❌ 加载排课结果失败: {e}")
            return []

    def find_missing_courses(
        self, all_courses: List[Course], selected_courses: List[SelectedCourse]
    ) -> List[Course]:
        """找出缺失的课程"""
        print("🔍 正在分析缺失课程...")

        # 获取已选课程的编码集合
        selected_codes = set(sc.course.code for sc in selected_courses)

        # 找出缺失的课程
        missing_courses = []
        missing_online = 0
        missing_offline = 0

        for course in all_courses:
            if course.code not in selected_codes:
                missing_courses.append(course)
                if self.is_online_course(course):
                    missing_online += 1
                else:
                    missing_offline += 1

        self.stats["missing_courses"] = len(missing_courses)
        self.stats["missing_online_courses"] = missing_online
        self.stats["missing_offline_courses"] = missing_offline

        print(f"📊 发现 {len(missing_courses)} 门缺失课程")
        print(f"   📱 线上课程: {missing_online} 门")
        print(f"   🏫 线下课程: {missing_offline} 门")

        return missing_courses

    def _parse_time_from_excel_row(self, row) -> List[TimeSlot]:
        """从Excel行解析时间信息"""
        time_slots = []

        # 检查可能的时间列名
        time_columns = []
        for col in row.index:
            if any(
                keyword in str(col)
                for keyword in [
                    "星期",
                    "节次",
                    "周次",
                    "时间",
                    "weekday",
                    "section",
                    "week",
                ]
            ):
                time_columns.append(col)

        if time_columns:
            print(f"   发现时间相关列: {time_columns}")

        # 尝试解析多个时间段（星期几1, 节次1, 周次1, 星期几2, 节次2, 周次2, ...）
        for i in range(1, 6):  # 最多5个时间段
            weekday_col = None
            section_col = None
            weeks_col = None

            # 查找对应的列名
            for col in row.index:
                if f"星期几{i}" in str(col) or f"weekday{i}" in str(col).lower():
                    weekday_col = col
                elif f"节次{i}" in str(col) or f"section{i}" in str(col).lower():
                    section_col = col
                elif f"周次{i}" in str(col) or f"week{i}" in str(col).lower():
                    weeks_col = col

            # 如果找到完整的时间段信息
            if weekday_col and section_col:
                try:
                    weekday_val = row[weekday_col]
                    section_val = row[section_col]
                    weeks_val = row[weeks_col] if weeks_col else "1-20"

                    # 检查是否有有效数据
                    if (
                        pd.notna(weekday_val)
                        and pd.notna(section_val)
                        and str(weekday_val).strip()
                        and str(section_val).strip()
                    ):
                        time_slot = self._create_time_slot(
                            weekday_val, section_val, weeks_val, i
                        )
                        if time_slot:
                            time_slots.append(time_slot)
                            print(f"   ✅ 解析时间段{i}: {time_slot}")

                except Exception as e:
                    print(f"   ❌ 解析时间段{i}失败: {e}")

        return time_slots

    def _create_time_slot(
        self, weekday_val, section_val, weeks_val, slot_num: int
    ) -> Optional[TimeSlot]:
        """创建时间段对象"""
        try:
            print(
                f"   🔧 创建时间段{slot_num}: 星期{weekday_val}, 节次{section_val}, 周次{weeks_val}"
            )

            # 解析星期几
            if isinstance(weekday_val, str):
                weekday_map = {
                    "一": 1,
                    "二": 2,
                    "三": 3,
                    "四": 4,
                    "五": 5,
                    "六": 6,
                    "日": 7,
                }
                weekday = weekday_map.get(
                    weekday_val, int(weekday_val) if weekday_val.isdigit() else 1
                )
            else:
                weekday = int(weekday_val)

            print(f"   📅 解析星期几: {weekday_val} -> {weekday}")

            # 解析节次
            section_str = str(section_val).strip()
            if "-" in section_str:
                start_section, end_section = map(int, section_str.split("-"))
            else:
                start_section = end_section = int(section_str)

            print(f"   ⏰ 解析节次: {section_val} -> {start_section}-{end_section}")

            # 解析周次
            weeks_str = str(weeks_val).strip() if pd.notna(weeks_val) else "1-20"
            if "-" in weeks_str:
                start_week, end_week = map(int, weeks_str.split("-"))
                weeks = list(range(start_week, end_week + 1))
            else:
                weeks = [int(weeks_str)]

            print(f"   📆 解析周次: {weeks_val} -> {weeks[0]}-{weeks[-1]}周")

            time_slot = TimeSlot(
                weekday=weekday,
                start_section=start_section,
                end_section=end_section,
                weeks=weeks,
            )

            print(f"   ✅ 成功创建时间段: {time_slot}")
            return time_slot

        except Exception as e:
            print(f"   ❌ 创建时间段{slot_num}失败: {e}")
            print(f"   原始数据: 星期{weekday_val}, 节次{section_val}, 周次{weeks_val}")
            return None

    def parse_time_info(self, course: Course) -> List[TimeSlot]:
        """解析课程时间信息"""
        print("   🔍 解析时间信息...")

        # 从存储的时间信息中获取
        if hasattr(self, "course_time_info") and course.code in self.course_time_info:
            time_slots = self.course_time_info[course.code]
            print(f"   📊 从存储中获取到 {len(time_slots)} 个时间段")
            return time_slots
        else:
            print(f"   ⚠️ 未找到课程 {course.code} 的时间信息")
            return []

    def is_online_course(self, course: Course) -> bool:
        """判断是否为线上课程"""
        # 优先使用从Excel"是否线上"列解析的信息
        if (
            hasattr(self, "course_online_info")
            and course.code in self.course_online_info
        ):
            is_online = self.course_online_info[course.code]
            print(f"   📱 使用Excel线上状态: {course.code} -> {is_online}")
            return is_online

        # 备用方案：使用关键词匹配识别逻辑
        print(f"   ⚠️ 未找到Excel线上状态，使用关键词匹配: {course.code}")
        online_indicators = ["系统所", "线上", "网络", "远程", "在线"]

        # 检查校区字段
        if any(indicator in course.campus for indicator in online_indicators):
            return True

        # 检查课程名称
        if any(indicator in course.name for indicator in online_indicators):
            return True

        # 检查开课院系
        if any(indicator in course.department for indicator in online_indicators):
            return True

        return False

    def create_selected_course(self, course: Course) -> SelectedCourse:
        """创建已选课程对象"""
        # 判断是否为线上课程
        is_online = self.is_online_course(course)

        print(f"   📋 课程类型判断: {'线上' if is_online else '线下'}")

        if is_online:
            # 线上课程没有固定时间段，但仍可能有时间冲突（如直播时间）
            time_slots = []
            print("   ⏰ 线上课程，无固定时间段")
        else:
            # 尝试解析时间信息
            time_slots = self.parse_time_info(course)

            # 如果没有时间信息，跳过该课程（不创建默认时间段）
            if not time_slots:
                print("   ⚠️ 线下课程缺少时间信息，跳过添加")
                return None

            print(f"   ⏰ 线下课程，时间段: {len(time_slots)}个")

        selected_course = SelectedCourse(
            course=course,
            class_num=course.class_num if hasattr(course, "class_num") else 1,
            time_slots=time_slots,
            is_online=is_online,
            custom_category="",  # 将自动分配
            is_imported=False,
        )

        return selected_course

    def check_constraints(
        self, candidate: SelectedCourse, current_schedule: List[SelectedCourse]
    ) -> Tuple[bool, List[str]]:
        """检查约束条件"""
        conflicts = []

        print("   🔍 开始约束检查...")

        # 创建临时课程列表进行检查
        temp_schedule = current_schedule + [candidate]

        # 检查时间冲突（线上和线下课程都需要检查）
        time_conflicts = self.constraint_checker.check_time_conflicts(temp_schedule)
        if time_conflicts:
            print(f"   ❌ 发现时间冲突: {len(time_conflicts)}个")
            for conflict in time_conflicts:
                print(f"      - {conflict.description}")
                conflicts.append(f"时间冲突: {conflict.description}")
            self.stats["time_conflicts"] += 1
        else:
            print("   ✅ 无时间冲突")

        # 检查校区冲突（仅对线下课程）
        if not candidate.is_online:
            campus_conflicts = self.constraint_checker.check_campus_conflicts(
                temp_schedule
            )
            if campus_conflicts:
                print(f"   ❌ 发现校区冲突: {len(campus_conflicts)}个")
                for conflict in campus_conflicts:
                    print(f"      - {conflict.description}")
                    conflicts.append(f"校区冲突: {conflict.description}")
                self.stats["campus_conflicts"] += 1
            else:
                print("   ✅ 无校区冲突")
        else:
            print("   ⏭️ 线上课程，跳过校区冲突检查")

        # 检查学分类别验证
        print(f"   🔍 检查学分类别: {candidate.custom_category}")
        if candidate.custom_category == "nan":
            # 为公共必修课提供智能默认分类
            if "公共必修" in candidate.course.category:
                candidate.custom_category = "公共必修课 - 公共必修"  # 默认选择
                print(
                    f"   🔄 智能修正类别: {candidate.course.code} -> {candidate.custom_category}"
                )
            else:
                conflicts.append("课程类别未设置，需要手动指定")
                print(f"   ❌ 类别验证失败: {candidate.course.code} 类别为 nan")

        # 验证类别是否被学分管理器支持
        requirement = self.credit_manager.get_requirement(candidate.custom_category)
        if not requirement:
            conflicts.append(f"不支持的课程类别: {candidate.custom_category}")
            print(f"   ❌ 不支持的类别: {candidate.custom_category}")
        else:
            print(f"   ✅ 类别验证通过: {candidate.custom_category}")

        return len(conflicts) == 0, conflicts

    def attempt_add_course(
        self, course: Course, current_schedule: List[SelectedCourse]
    ) -> Tuple[bool, List[str]]:
        """尝试添加课程"""
        try:
            # 创建候选课程
            candidate = self.create_selected_course(course)

            # 如果创建失败（如线下课程缺少时间信息），跳过
            if candidate is None:
                error_msg = "线下课程缺少时间信息"
                print(f"   ⏭️ 跳过课程: {error_msg}")
                self.failed_courses.append((course, [error_msg]))
                self.stats["failed_to_add"] += 1
                self.stats["other_conflicts"] += 1
                if self.is_online_course(course):
                    self.stats["failed_online"] += 1
                else:
                    self.stats["failed_offline"] += 1
                return False, [error_msg]

            # 检查约束条件
            can_add, conflicts = self.check_constraints(candidate, current_schedule)

            if can_add:
                print(f"   ✅ 可以添加课程: {course.code} - {course.name}")
                self.added_courses.append(candidate)
                self.stats["successfully_added"] += 1
                if candidate.is_online:
                    self.stats["successfully_added_online"] += 1
                else:
                    self.stats["successfully_added_offline"] += 1
                return True, []
            else:
                print(f"   ❌ 无法添加课程: {course.code} - {course.name}")
                for conflict in conflicts:
                    print(f"      冲突原因: {conflict}")
                self.failed_courses.append((course, conflicts))
                self.stats["failed_to_add"] += 1
                if self.is_online_course(course):
                    self.stats["failed_online"] += 1
                else:
                    self.stats["failed_offline"] += 1
                return False, conflicts

        except Exception as e:
            error_msg = f"处理课程时出错: {str(e)}"
            print(f"   ❌ {course.code} - {error_msg}")
            self.failed_courses.append((course, [error_msg]))
            self.stats["failed_to_add"] += 1
            self.stats["other_conflicts"] += 1
            if self.is_online_course(course):
                self.stats["failed_online"] += 1
            else:
                self.stats["failed_offline"] += 1
            return False, [error_msg]

    def supplement_courses(
        self, missing_courses: List[Course], current_schedule: List[SelectedCourse]
    ) -> List[SelectedCourse]:
        """补充课程（穷举法）"""
        print(f"\n🔄 开始尝试添加 {len(missing_courses)} 门缺失课程...")
        print(f"📋 当前排课结果包含 {len(current_schedule)} 门课程")

        # 复制当前排课结果
        updated_schedule = current_schedule.copy()

        # 按课程类型分组处理（优先处理线上课程）
        online_courses = [c for c in missing_courses if self.is_online_course(c)]
        offline_courses = [c for c in missing_courses if not self.is_online_course(c)]

        print(
            f"📊 课程分类: {len(online_courses)} 门线上课程, {len(offline_courses)} 门线下课程"
        )

        # 先处理线上课程（通常没有冲突）
        all_courses_to_process = online_courses + offline_courses

        # 逐个尝试添加课程
        for i, course in enumerate(all_courses_to_process, 1):
            course_type = "线上" if self.is_online_course(course) else "线下"
            print(
                f"\n[{i}/{len(all_courses_to_process)}] 尝试添加 {course_type} 课程: {course.code} - {course.name}"
            )
            print(
                f"   课程信息: {course.department} | {course.campus} | {course.credits}学分"
            )

            success, _ = self.attempt_add_course(course, updated_schedule)

            if success:
                # 添加成功，更新排课结果
                if self.added_courses:
                    updated_schedule.append(self.added_courses[-1])
                    print(
                        f"   ✅ 成功添加到排课结果 (当前总数: {len(updated_schedule)})"
                    )

        print(
            f"\n📊 补充完成: 原有 {len(current_schedule)} 门课程 → 现有 {len(updated_schedule)} 门课程"
        )
        print(f"📈 新增 {len(updated_schedule) - len(current_schedule)} 门课程")

        return updated_schedule

    def export_results(self, updated_schedule: List[SelectedCourse]):
        """导出结果"""
        print(f"\n💾 正在导出结果到: {self.output_file}")

        try:
            success = self.exporter.export_to_excel(updated_schedule, self.output_file)
            if success:
                print("✅ 结果导出成功")
            else:
                print("❌ 结果导出失败")
        except Exception as e:
            print(f"❌ 导出失败: {e}")

    def print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 70)
        print("📊 课程补充测试统计报告")
        print("=" * 70)

        print(f"📚 课程一览表总数: {self.stats['total_courses_in_list']}")
        print(f"📋 原排课结果数量: {self.stats['total_courses_in_schedule']}")
        print(f"🔍 发现缺失课程: {self.stats['missing_courses']}")
        print(f"   📱 缺失线上课程: {self.stats['missing_online_courses']}")
        print(f"   🏫 缺失线下课程: {self.stats['missing_offline_courses']}")

        print(f"\n✅ 成功添加课程: {self.stats['successfully_added']}")
        print(f"   📱 成功添加线上: {self.stats['successfully_added_online']}")
        print(f"   🏫 成功添加线下: {self.stats['successfully_added_offline']}")

        print(f"\n❌ 无法添加课程: {self.stats['failed_to_add']}")
        print(f"   📱 失败线上课程: {self.stats['failed_online']}")
        print(f"   🏫 失败线下课程: {self.stats['failed_offline']}")

        print("\n🔍 冲突类型统计:")
        print(f"⏰ 时间冲突: {self.stats['time_conflicts']}")
        print(f"🏫 校区冲突: {self.stats['campus_conflicts']}")
        print(f"🔧 其他问题: {self.stats['other_conflicts']}")

        # 计算成功率
        if self.stats["missing_courses"] > 0:
            success_rate = (
                self.stats["successfully_added"] / self.stats["missing_courses"]
            ) * 100
            print(f"\n📈 总体成功率: {success_rate:.1f}%")

            if self.stats["missing_online_courses"] > 0:
                online_success_rate = (
                    self.stats["successfully_added_online"]
                    / self.stats["missing_online_courses"]
                ) * 100
                print(f"📱 线上课程成功率: {online_success_rate:.1f}%")

            if self.stats["missing_offline_courses"] > 0:
                offline_success_rate = (
                    self.stats["successfully_added_offline"]
                    / self.stats["missing_offline_courses"]
                ) * 100
                print(f"🏫 线下课程成功率: {offline_success_rate:.1f}%")

        if self.added_courses:
            print("\n✅ 成功添加的课程:")
            for course in self.added_courses:
                status = "线上" if course.is_online else "线下"
                print(f"   • {course.course.code} - {course.course.name} ({status})")

        if self.failed_courses:
            print("\n❌ 无法添加的课程 (显示前10个):")
            for course, conflicts in self.failed_courses[:10]:
                status = "线上" if self.is_online_course(course) else "线下"
                print(f"   • {course.code} - {course.name} ({status})")
                for conflict in conflicts[:2]:  # 只显示前2个冲突原因
                    print(f"     - {conflict}")

            if len(self.failed_courses) > 10:
                print(f"   ... 还有 {len(self.failed_courses) - 10} 门课程无法添加")

        print("=" * 70)

    def run(self):
        """运行测试"""
        print("🚀 开始课程补充测试...")
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. 加载数据
        all_courses = self.load_course_list()
        if not all_courses:
            return

        current_schedule = self.load_schedule_result(all_courses)
        if not current_schedule:
            return

        # 2. 找出缺失课程
        missing_courses = self.find_missing_courses(all_courses, current_schedule)
        if not missing_courses:
            print("🎉 没有发现缺失课程，排课结果已经完整！")
            return

        # 3. 尝试补充课程
        updated_schedule = self.supplement_courses(missing_courses, current_schedule)

        # 4. 导出结果
        self.export_results(updated_schedule)

        # 5. 打印统计信息
        self.print_statistics()

        print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🎉 课程补充测试完成！")


if __name__ == "__main__":
    tester = CourseSupplementTester()
    tester.run()
