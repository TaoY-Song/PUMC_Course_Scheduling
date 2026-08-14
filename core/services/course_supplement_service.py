#!/usr/bin/env python3
"""Wrapper service around the course supplement test script."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

scripts_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "scripts",
)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)


def _get_course_supplement_tester():
    from scripts.course_supplement_test import CourseSupplementTester

    return CourseSupplementTester


class CourseSupplementService:
    """UI-friendly wrapper for ``scripts/course_supplement_test.py``."""

    def __init__(
        self,
        *,
        log_file_path: Optional[str] = None,
        output_file_name: str = "补充后排课结果.xlsx",
    ):
        self.tester = None
        self.last_error = None
        self.log_file_path = log_file_path
        self.output_file_name = output_file_name
        self._setup_logging()

    def _setup_logging(self) -> None:
        try:
            if not self.log_file_path:
                self.log_file_path = "课程补充测试.log"

            log_path = Path(self.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            self.logger = logging.getLogger(f"CourseSupplementService:{id(self)}")
            self.logger.setLevel(logging.INFO)
            self.logger.handlers.clear()
            self.logger.propagate = False

            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

            file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
        except Exception as error:
            print(f"设置日志失败: {error}")
            self.log_file_path = None

    def _log_and_print(self, message: str, level: str = "INFO") -> None:
        print(message)
        if not hasattr(self, "logger"):
            return

        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def validate_files(
        self,
        schedule_result_file: str,
        course_list_file: str,
    ) -> Tuple[bool, str]:
        try:
            if not os.path.exists(schedule_result_file):
                return False, f"排课结果文件不存在: {schedule_result_file}"

            if not os.path.exists(course_list_file):
                return False, f"备选课程表文件不存在: {course_list_file}"

            if not schedule_result_file.lower().endswith((".xlsx", ".xls")):
                return False, "排课结果文件必须是 Excel 文件"

            if not course_list_file.lower().endswith((".xlsx", ".xls")):
                return False, "备选课程表文件必须是 Excel 文件"

            import pandas as pd

            try:
                schedule_df = pd.read_excel(schedule_result_file, sheet_name="课程列表")
                required_schedule_columns = ["课程编码", "课程名称", "学分"]
                missing_schedule_cols = [
                    column for column in required_schedule_columns if column not in schedule_df.columns
                ]
                if missing_schedule_cols:
                    return False, f"排课结果文件缺少必要列: {', '.join(missing_schedule_cols)}"
            except Exception as error:
                return False, f"排课结果文件格式错误: {error}"

            try:
                course_df = pd.read_excel(course_list_file)
                required_course_columns = [
                    "课程编码",
                    "课程名称",
                    "学分",
                    "开课院系",
                    "课程类别",
                ]
                missing_course_cols = [
                    column for column in required_course_columns if column not in course_df.columns
                ]
                if missing_course_cols:
                    return False, f"备选课程表缺少必要列: {', '.join(missing_course_cols)}"
            except Exception as error:
                return False, f"备选课程表格式错误: {error}"

            return True, "文件校验通过"
        except Exception as error:
            return False, f"文件校验失败: {error}"

    def run_supplement_test(
        self,
        schedule_result_file: str,
        course_list_file: str,
    ) -> Dict:
        try:
            is_valid, error_msg = self.validate_files(schedule_result_file, course_list_file)
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "added_courses": [],
                    "failed_courses": [],
                    "stats": {},
                }

            CourseSupplementTester = _get_course_supplement_tester()
            self.tester = CourseSupplementTester()
            self.tester.course_list_file = course_list_file
            self.tester.schedule_result_file = schedule_result_file

            output_dir = os.path.dirname(schedule_result_file)
            self.tester.output_file = os.path.join(output_dir, self.output_file_name)

            self._log_and_print("开始运行课程补充测试")
            self._log_and_print(f"排课结果文件: {schedule_result_file}")
            self._log_and_print(f"课程源文件: {course_list_file}")
            self._log_and_print(f"输出文件: {self.tester.output_file}")
            if self.log_file_path:
                self._log_and_print(f"日志文件: {self.log_file_path}")

            self.tester.run()

            # tester 在“没有缺失课程”时会提前返回且不写输出文件。
            # Web API 已经承诺运行后可下载补充结果，因此无论有没有新增，
            # 都必须产出一个有效结果文件。无缺失时原结果就是最终结果，
            # 直接复制，避免页面只出现日志下载入口。
            output_path = Path(self.tester.output_file)
            if not output_path.exists():
                source_path = Path(schedule_result_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, output_path)
                self._log_and_print("未发现缺失课程，已将原排课结果作为补充结果输出")

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
                    {
                        "code": course.code,
                        "name": course.name,
                        "reasons": reasons,
                    }
                    for course, reasons in self.tester.failed_courses
                ],
                "stats": dict(self.tester.stats),
                "output_file": self.tester.output_file,
            }

            self._log_and_print("课程补充测试完成")
            self._log_and_print(f"成功补入课程: {len(result['added_courses'])} 门")
            self._log_and_print(f"未补入课程: {len(result['failed_courses'])} 门")

            return result
        except Exception as error:
            self.last_error = str(error)
            self._log_and_print(f"课程补充测试失败: {error}", "ERROR")

            import traceback

            self._log_and_print(traceback.format_exc(), "ERROR")
            return {
                "success": False,
                "error": f"课程补充测试失败: {error}",
                "added_courses": [],
                "failed_courses": [],
                "stats": {},
            }

    def get_simple_result_message(self, result: Dict) -> str:
        if not result["success"]:
            return f"测试失败: {result['error']}"

        added_courses = result["added_courses"]
        if not added_courses:
            return "没有找到可以补充的课程"

        course_list = []
        for course in added_courses:
            course_type = "线上" if course["is_online"] else "线下"
            course_list.append(f"{course['name']}({course_type}, {course['credits']}学分)")

        return "成功补充的课程:\n" + "\n".join(f"- {course}" for course in course_list)

    def get_output_file_path(self) -> Optional[str]:
        if self.tester:
            return getattr(self.tester, "output_file", None)
        return None
