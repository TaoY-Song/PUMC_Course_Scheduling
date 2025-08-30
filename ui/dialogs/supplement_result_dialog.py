#!/usr/bin/env python3
"""
课程补充测试结果对话框
"""

import os
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QGroupBox,
)
from typing import Dict


class SupplementResultDialog(QDialog):
    """课程补充测试结果对话框"""

    def __init__(self, result: Dict, log_file_path: str = None, parent=None):
        super().__init__(parent)
        self.result = result
        self.log_file_path = log_file_path
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("课程补充测试结果")
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout()

        # 结果显示区域
        result_group = QGroupBox("测试结果")
        result_layout = QVBoxLayout()

        # 结果文本
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(250)

        # 设置结果内容
        self._set_result_content()

        result_layout.addWidget(self.result_text)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 查看详细日志按钮
        self.view_log_button = QPushButton("查看详细日志")
        self.view_log_button.clicked.connect(self.view_detailed_log)
        button_layout.addWidget(self.view_log_button)

        # 打开输出文件按钮（仅成功时显示）
        if self.result["success"] and self.result.get("output_file"):
            self.open_file_button = QPushButton("打开补充结果文件")
            self.open_file_button.clicked.connect(self.open_output_file)
            button_layout.addWidget(self.open_file_button)

        button_layout.addStretch()

        # 关闭按钮
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setDefault(True)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _set_result_content(self):
        """设置结果内容"""
        if not self.result["success"]:
            # 失败情况
            content = f"❌ 测试失败\n\n错误原因:\n{self.result['error']}\n\n"
            content += "请检查文件格式和内容是否正确。\n"
            content += "详细错误信息请查看日志文件。"
            self.result_text.setStyleSheet("color: #d32f2f;")
        else:
            # 成功情况
            added_courses = self.result["added_courses"]
            stats = self.result.get("stats", {})

            if not added_courses:
                content = "ℹ️ 测试完成\n\n没有找到可以补充的课程。\n"
                content += "这可能意味着当前排课结果已经包含了所有可用的课程，\n"
                content += "或者剩余课程存在时间冲突或其他约束问题。"
                self.result_text.setStyleSheet("color: #1976d2;")
            else:
                content = (
                    f"✅ 测试成功完成\n\n成功添加了 {len(added_courses)} 门课程:\n\n"
                )

                for i, course in enumerate(added_courses, 1):
                    course_type = "线上" if course["is_online"] else "线下"
                    content += f"{i}. {course['name']}\n"
                    content += f"   课程编码: {course['code']}\n"
                    content += f"   学分: {course['credits']} | 类型: {course_type}\n"
                    content += f"   类别: {course['category']}\n\n"

                # 添加统计信息
                if stats:
                    success_rate = (
                        stats.get("successfully_added", 0)
                        / max(stats.get("missing_courses", 1), 1)
                    ) * 100
                    content += "📊 统计信息:\n"
                    content += f"• 总体成功率: {success_rate:.1f}%\n"
                    content += f"• 成功添加: {stats.get('successfully_added', 0)} 门\n"
                    content += f"• 无法添加: {stats.get('failed_to_add', 0)} 门\n"

                self.result_text.setStyleSheet("color: #388e3c;")

        self.result_text.setPlainText(content)

    def view_detailed_log(self):
        """查看详细日志"""
        try:
            # 使用传入的独立日志文件路径
            if self.log_file_path and os.path.exists(self.log_file_path):
                # 在Windows上使用默认程序打开日志文件
                import subprocess
                import platform

                if platform.system() == "Windows":
                    os.startfile(self.log_file_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", self.log_file_path])
                else:  # Linux
                    subprocess.run(["xdg-open", self.log_file_path])
            else:
                if not self.log_file_path:
                    QMessageBox.warning(self, "警告", "没有可用的日志文件路径")
                else:
                    QMessageBox.warning(
                        self, "警告", f"日志文件不存在: {self.log_file_path}"
                    )

        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开日志文件: {str(e)}")

    def open_output_file(self):
        """打开输出文件"""
        try:
            output_file = self.result.get("output_file")
            if output_file and os.path.exists(output_file):
                # 在Windows上使用默认程序打开Excel文件
                import subprocess
                import platform

                if platform.system() == "Windows":
                    os.startfile(output_file)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", output_file])
                else:  # Linux
                    subprocess.run(["xdg-open", output_file])
            else:
                QMessageBox.warning(self, "警告", f"输出文件不存在: {output_file}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开输出文件: {str(e)}")
