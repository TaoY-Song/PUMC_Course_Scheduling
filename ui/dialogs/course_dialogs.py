#!/usr/bin/env python3
"""
对话框组件
包含时间段配置对话框等UI组件
"""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QGridLayout,
    QMessageBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QDoubleSpinBox,
)
from PyQt5.QtCore import Qt
from core.models import TimeSlot, SelectedCourse
from core.credit_manager import CreditManager


class TimeSlotDialog(QDialog):
    """时间段配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_time_slot = None  # 存储结果
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 星期几选择
        weekday_layout = QHBoxLayout()
        weekday_layout.addWidget(QLabel("星期几:"))
        self.weekday_combo = QComboBox()
        self.weekday_combo.addItems(
            ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        )
        weekday_layout.addWidget(self.weekday_combo)
        layout.addLayout(weekday_layout)

        # 节次选择
        section_layout = QHBoxLayout()
        section_layout.addWidget(QLabel("开始节次:"))
        self.start_section = QSpinBox()
        self.start_section.setRange(1, 10)
        self.start_section.setValue(1)
        section_layout.addWidget(self.start_section)

        section_layout.addWidget(QLabel("结束节次:"))
        self.end_section = QSpinBox()
        self.end_section.setRange(1, 10)
        self.end_section.setValue(2)
        section_layout.addWidget(self.end_section)
        layout.addLayout(section_layout)

        # 周次选择 - 使用20个可点击的小方块
        weeks_layout = QVBoxLayout()
        weeks_layout.addWidget(QLabel("选择上课周次:"))

        # 快捷操作按钮
        quick_buttons_layout = QHBoxLayout()
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self.select_all_weeks)
        quick_buttons_layout.addWidget(self.select_all_button)

        self.clear_all_button = QPushButton("清空")
        self.clear_all_button.clicked.connect(self.clear_all_weeks)
        quick_buttons_layout.addWidget(self.clear_all_button)

        weeks_layout.addLayout(quick_buttons_layout)

        # 20个周次选择按钮
        self.week_buttons = []
        weeks_grid = QGridLayout()

        for week in range(1, 21):
            button = QPushButton(str(week))
            button.setCheckable(True)
            button.setFixedSize(35, 35)
            button.clicked.connect(self.on_week_button_clicked)
            self.week_buttons.append(button)

            # 排列成4行5列
            row = (week - 1) // 5
            col = (week - 1) % 5
            weeks_grid.addWidget(button, row, col)

        weeks_widget = QDialog()
        weeks_widget.setLayout(weeks_grid)
        weeks_layout.addWidget(weeks_widget)

        # 默认选择前10周
        for i in range(10):
            self.week_buttons[i].setChecked(True)

        # 更新按钮样式
        self.update_week_button_styles()

        layout.addLayout(weeks_layout)

        # 添加按钮
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("添加时间段")
        self.add_button.clicked.connect(self.add_time_slot)
        button_layout.addWidget(self.add_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setWindowTitle("添加时间段")
        self.resize(400, 350)

    def select_all_weeks(self):
        """全选所有周次"""
        for button in self.week_buttons:
            button.setChecked(True)
        self.update_week_button_styles()

    def clear_all_weeks(self):
        """清空所有周次选择"""
        for button in self.week_buttons:
            button.setChecked(False)
        self.update_week_button_styles()

    def on_week_button_clicked(self):
        """周次按钮点击处理"""
        # 更新按钮样式
        self.update_week_button_styles()

    def update_week_button_styles(self):
        """更新周次按钮样式"""
        for button in self.week_buttons:
            if button.isChecked():
                button.setStyleSheet(
                    "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }"
                )
            else:
                button.setStyleSheet(
                    "QPushButton { background-color: #f0f0f0; color: black; }"
                )

    def get_selected_weeks(self):
        """获取选中的周次列表"""
        selected_weeks = []
        for i, button in enumerate(self.week_buttons):
            if button.isChecked():
                selected_weeks.append(i + 1)
        return selected_weeks

    def add_time_slot(self):
        """添加时间段"""
        try:
            weekday = self.weekday_combo.currentIndex() + 1
            start_section = self.start_section.value()
            end_section = self.end_section.value()

            if start_section > end_section:
                QMessageBox.warning(self, "错误", "开始节次不能大于结束节次")
                return

            # 获取选中的周次
            weeks = self.get_selected_weeks()
            if not weeks:
                QMessageBox.warning(self, "错误", "请至少选择一个上课周次")
                return

            # 创建时间段
            time_slot = TimeSlot(
                weekday=weekday,
                start_section=start_section,
                end_section=end_section,
                weeks=weeks,
            )

            # 将结果存储在dialog中
            self.result_time_slot = time_slot
            self.accept()  # 关闭对话框并返回Accepted

        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加时间段失败: {str(e)}")


class CategorySettingDialog(QDialog):
    """课程类别设置对话框"""

    def __init__(self, selected_course: SelectedCourse, parent=None):
        super().__init__(parent)
        self.selected_course = selected_course
        self.result_category = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 课程信息显示
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel("课程信息:"))

        course_info = QTextEdit()
        course_info.setMaximumHeight(120)
        course_info.setReadOnly(True)

        info_text = (
            f"课程编码: {self.selected_course.course.code}\n"
            f"课程名称: {self.selected_course.course.name}\n"
            f"班次: {self.selected_course.class_num}\n"
            f"原始类别: {self.selected_course.course.category}\n"
            f"任课教师: {self.selected_course.course.teacher}"
        )
        course_info.setText(info_text)
        info_layout.addWidget(course_info)
        layout.addLayout(info_layout)

        # 类别选择
        category_layout = QVBoxLayout()

        # 当前类别显示
        current_label = QLabel(f"当前类别: {self.selected_course.custom_category}")
        current_label.setStyleSheet("font-weight: bold; color: #2E8B57;")
        category_layout.addWidget(current_label)

        # 类别选择说明
        explanation = QLabel("请选择课程类别:")
        category_layout.addWidget(explanation)

        # 类别选择下拉框
        self.category_combo = QComboBox()
        available_categories = self.selected_course.get_available_categories()
        self.category_combo.addItems(available_categories)

        # 设置当前选中项，安全处理可能的异常值
        try:
            current_index = available_categories.index(
                self.selected_course.custom_category
            )
            self.category_combo.setCurrentIndex(current_index)
        except ValueError:
            # 如果当前类别不在可用列表中（如NaN、空字符串等），默认选择第一个
            print(
                f"⚠️ 当前类别 '{self.selected_course.custom_category}' 不在可用列表中，使用默认选择"
            )
            self.category_combo.setCurrentIndex(0)
            # 同时更新课程的类别为第一个可用类别
            if available_categories:
                self.selected_course.custom_category = available_categories[0]

        category_layout.addWidget(self.category_combo)

        # 类别说明
        self._add_category_explanations(category_layout)

        layout.addLayout(category_layout)

        # 按钮
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.save_category)
        button_layout.addWidget(self.save_button)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setWindowTitle("课程类别设置")
        self.resize(500, 400)

    def _add_category_explanations(self, layout):
        """添加类别说明"""
        explanations = QTextEdit()
        explanations.setMaximumHeight(100)
        explanations.setReadOnly(True)

        original_category = self.selected_course.course.category

        if "公共必修" in original_category:
            explanation_text = (
                "类别说明:\n"
                "• 公共必修课 - 公共必修: 普通的公共必修课程\n"
                "• 公共必修课 - 公共必修（二选一）: 需要从多门课程中选择一门的公共必修课"
            )
        else:
            explanation_text = (
                "类别说明:\n"
                "• 选修课 - 学位选修: 与学位相关的选修课程\n"
                "• 学位必修课（核心课）: 学位要求的核心必修课程"
            )

        explanations.setText(explanation_text)
        layout.addWidget(explanations)

    def save_category(self):
        """保存类别设置"""
        selected_category = self.category_combo.currentText()

        if self.selected_course.set_custom_category(selected_category):
            self.result_category = selected_category
            QMessageBox.information(
                self, "成功", f"课程类别已设置为: {selected_category}"
            )
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "设置课程类别失败")

    def close(self):
        """关闭对话框"""
        self.reject()


class CreditSettingsDialog(QDialog):
    """学分设置对话框"""

    def __init__(self, credit_manager: CreditManager, parent=None):
        super().__init__(parent)
        self.credit_manager = credit_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 说明
        info_label = QLabel("设置各类别课程的最低学分要求:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # 学分设置表格
        self.credit_table = QTableWidget()
        self.credit_table.setColumnCount(4)
        self.credit_table.setHorizontalHeaderLabels(
            ["课程类别", "要求学分", "已修学分", "未修学分"]
        )

        # 填充表格数据
        self.populate_table()

        layout.addWidget(self.credit_table)

        # 按钮
        button_layout = QHBoxLayout()

        self.reset_button = QPushButton("恢复默认")
        self.reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_button)

        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setWindowTitle("学分设置")
        self.resize(600, 400)

    def populate_table(self):
        """填充表格数据"""
        categories = list(self.credit_manager.requirements.keys())
        self.credit_table.setRowCount(len(categories))

        for i, category in enumerate(categories):
            req = self.credit_manager.get_requirement(category)

            # 类别名称（只读）
            category_item = QTableWidgetItem(category)
            category_item.setFlags(category_item.flags() & ~Qt.ItemIsEditable)
            self.credit_table.setItem(i, 0, category_item)

            # 要求学分（可编辑）
            required_spinbox = QDoubleSpinBox()
            required_spinbox.setRange(0.0, 50.0)
            required_spinbox.setSingleStep(0.5)
            required_spinbox.setValue(req.required_credits)
            self.credit_table.setCellWidget(i, 1, required_spinbox)

            # 已修学分（可编辑）
            completed_spinbox = QDoubleSpinBox()
            completed_spinbox.setRange(0.0, 50.0)
            completed_spinbox.setSingleStep(0.5)
            completed_spinbox.setValue(req.completed_credits)
            completed_spinbox.setToolTip("该类别已经完成的学分数")
            self.credit_table.setCellWidget(i, 2, completed_spinbox)

            # 未修学分（只读显示，自动计算）
            remaining_item = QTableWidgetItem(f"{req.remaining_credits:.1f}")
            remaining_item.setFlags(remaining_item.flags() & ~Qt.ItemIsEditable)
            remaining_item.setToolTip("未修学分 = 要求学分 - 已修学分")
            self.credit_table.setItem(i, 3, remaining_item)

        # 调整列宽
        self.credit_table.resizeColumnsToContents()

    def reset_to_default(self):
        """恢复默认设置"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要恢复到默认学分设置吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # 恢复默认值
            for i in range(self.credit_table.rowCount()):
                category_item = self.credit_table.item(i, 0)
                category = category_item.text()

                default_credits = self.credit_manager.DEFAULT_REQUIREMENTS.get(
                    category, 0.0
                )
                required_spinbox = self.credit_table.cellWidget(i, 1)
                if required_spinbox:
                    required_spinbox.setValue(default_credits)

                # 清空已修学分
                completed_spinbox = self.credit_table.cellWidget(i, 2)
                if completed_spinbox:
                    completed_spinbox.setValue(0.0)

    def save_settings(self):
        """保存设置"""
        try:
            # 更新学分要求和手动输入学分
            for i in range(self.credit_table.rowCount()):
                category_item = self.credit_table.item(i, 0)
                category = category_item.text()

                # 更新要求学分
                required_spinbox = self.credit_table.cellWidget(i, 1)
                if required_spinbox:
                    required_credits = required_spinbox.value()
                    self.credit_manager.set_required_credits(category, required_credits)

                # 更新已修学分
                completed_spinbox = self.credit_table.cellWidget(i, 2)
                if completed_spinbox:
                    completed_credits = completed_spinbox.value()
                    self.credit_manager.set_completed_credits(
                        category, completed_credits
                    )

            QMessageBox.information(self, "成功", "学分设置已保存")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置时出错: {str(e)}")
