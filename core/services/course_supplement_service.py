#!/usr/bin/env python3
"""
课程补充测试服务
封装 CourseSupplementTester 功能，提供UI友好的接口
"""

import os
import sys
import logging
from typing import Dict, Tuple, Optional

# 添加scripts目录到路径，以便导入CourseSupplementTester
scripts_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts"
)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

# 延迟导入以避免模块级别导入问题
def _get_course_supplement_tester():
    """获取CourseSupplementTester类"""
    from scripts.course_supplement_test import CourseSupplementTester
    return CourseSupplementTester


class CourseSupplementService:
    """课程补充测试服务"""

    def __init__(self):
        self.tester = None
        self.last_error = None
        self.log_file_path = None
        self._setup_logging()

    def _setup_logging(self):
        """设置独立的日志文件"""
        try:
            # 创建固定名称的日志文件，直接覆盖
            self.log_file_path = "课程补充测试.log"

            # 配置日志记录器
            self.logger = logging.getLogger("CourseSupplementService")
            self.logger.setLevel(logging.INFO)

            # 清除现有的处理器
            self.logger.handlers.clear()

            # 创建文件处理器，使用'w'模式直接覆盖文件
            file_handler = logging.FileHandler(
                self.log_file_path, mode="w", encoding="utf-8"
            )
            file_handler.setLevel(logging.INFO)

            # 创建控制台处理器（用于print输出重定向）
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            # 设置日志格式
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            # 添加处理器
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

        except Exception as e:
            print(f"设置日志文件失败: {e}")
            self.log_file_path = None

    def _log_and_print(self, message: str, level: str = "INFO"):
        """同时记录到日志文件和控制台"""
        print(message)  # 控制台输出
        if hasattr(self, "logger"):
            if level == "ERROR":
                self.logger.error(message)
            elif level == "WARNING":
                self.logger.warning(message)
            else:
                self.logger.info(message)

    def validate_files(
        self, schedule_result_file: str, course_list_file: str
    ) -> Tuple[bool, str]:
        """验证输入文件的有效性"""
        try:
            # 检查文件是否存在
            if not os.path.exists(schedule_result_file):
                return False, f"排课结果文件不存在: {schedule_result_file}"

            if not os.path.exists(course_list_file):
                return False, f"备选课程表文件不存在: {course_list_file}"

            # 检查文件扩展名
            if not schedule_result_file.lower().endswith(".xlsx"):
                return False, "排课结果文件必须是Excel格式(.xlsx)"

            if not course_list_file.lower().endswith(".xlsx"):
                return False, "备选课程表文件必须是Excel格式(.xlsx)"

            # 尝试读取文件以验证格式
            import pandas as pd

            try:
                # 验证排课结果文件
                schedule_df = pd.read_excel(schedule_result_file, sheet_name="课程列表")
                required_schedule_columns = ["课程编码", "课程名称", "学分"]
                missing_schedule_cols = [
                    col
                    for col in required_schedule_columns
                    if col not in schedule_df.columns
                ]
                if missing_schedule_cols:
                    return (
                        False,
                        f"排课结果文件缺少必要列: {', '.join(missing_schedule_cols)}",
                    )

            except Exception as e:
                return False, f"排课结果文件格式错误: {str(e)}"

            try:
                # 验证备选课程表文件
                course_df = pd.read_excel(course_list_file)
                required_course_columns = [
                    "课程编码",
                    "课程名称",
                    "学分",
                    "开课院系",
                    "课程类别",
                ]
                missing_course_cols = [
                    col
                    for col in required_course_columns
                    if col not in course_df.columns
                ]
                if missing_course_cols:
                    return (
                        False,
                        f"备选课程表文件缺少必要列: {', '.join(missing_course_cols)}",
                    )

            except Exception as e:
                return False, f"备选课程表文件格式错误: {str(e)}"

            return True, "文件验证通过"

        except Exception as e:
            return False, f"文件验证过程中出错: {str(e)}"

    def run_supplement_test(
        self, schedule_result_file: str, course_list_file: str
    ) -> Dict:
        """
        运行课程补充测试

        Args:
            schedule_result_file: 排课结果文件路径
            course_list_file: 备选课程表文件路径

        Returns:
            Dict: 包含测试结果的字典
        """
        try:
            # 验证文件
            is_valid, error_msg = self.validate_files(
                schedule_result_file, course_list_file
            )
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "added_courses": [],
                    "failed_courses": [],
                    "stats": {},
                }

            # 创建测试器实例
            CourseSupplementTester = _get_course_supplement_tester()
            self.tester = CourseSupplementTester()

            # 设置文件路径（替换硬编码路径）
            self.tester.course_list_file = course_list_file
            self.tester.schedule_result_file = schedule_result_file

            # 设置输出文件路径（在同一目录下）
            output_dir = os.path.dirname(schedule_result_file)
            self.tester.output_file = os.path.join(output_dir, "补充后排课结果.xlsx")

            self._log_and_print("🚀 开始课程补充测试...")
            self._log_and_print(f"📋 排课结果文件: {schedule_result_file}")
            self._log_and_print(f"📚 备选课程表文件: {course_list_file}")
            self._log_and_print(f"💾 输出文件: {self.tester.output_file}")
            self._log_and_print(f"📝 详细日志文件: {self.log_file_path}")

            # 运行测试
            self.tester.run()

            # 提取结果
            result = {
                "success": True,
                "error": None,
                "added_courses": [
                    {
                        "code": course.course.code,
                        "name": course.course.name,
                        "credits": course.course.credits,
                        "category": course.custom_category,
                        "is_online": course.is_online,
                    }
                    for course in self.tester.added_courses
                ],
                "failed_courses": [
                    {"code": course.code, "name": course.name, "reasons": reasons}
                    for course, reasons in self.tester.failed_courses
                ],
                "stats": dict(self.tester.stats),
                "output_file": self.tester.output_file,
            }

            self._log_and_print("✅ 课程补充测试完成")

            # 记录详细结果到日志
            self._log_and_print("📊 测试结果统计:")
            self._log_and_print(f"   成功添加课程: {len(result['added_courses'])} 门")
            self._log_and_print(f"   无法添加课程: {len(result['failed_courses'])} 门")

            for course in result["added_courses"]:
                self._log_and_print(
                    f"   ✅ {course['name']} ({course['code']}, {course['credits']}学分)"
                )

            for course_info in result["failed_courses"]:
                self._log_and_print(
                    f"   ❌ {course_info['name']} ({course_info['code']}) - 原因: {', '.join(course_info['reasons'])}"
                )

            return result

        except Exception as e:
            error_msg = f"课程补充测试过程中出错: {str(e)}"
            self._log_and_print(f"❌ {error_msg}", "ERROR")

            # 记录详细错误信息到日志
            import traceback

            error_details = traceback.format_exc()
            self._log_and_print("详细错误堆栈:", "ERROR")
            self._log_and_print(error_details, "ERROR")

            return {
                "success": False,
                "error": error_msg,
                "added_courses": [],
                "failed_courses": [],
                "stats": {},
            }

    def get_simple_result_message(self, result: Dict) -> str:
        """获取简化的结果消息，用于UI显示"""
        if not result["success"]:
            return f"❌ 测试失败: {result['error']}"

        added_courses = result["added_courses"]
        if not added_courses:
            return "ℹ️ 没有找到可以补充的课程"

        # 构建成功添加的课程列表
        course_list = []
        for course in added_courses:
            course_type = "线上" if course["is_online"] else "线下"
            course_list.append(
                f"{course['name']}({course_type}, {course['credits']}学分)"
            )

        return "✅ 成功添加的课程:\n" + "\n".join(
            f"• {course}" for course in course_list
        )

    def get_output_file_path(self) -> Optional[str]:
        """获取输出文件路径"""
        if self.tester:
            return getattr(self.tester, "output_file", None)
        return None
