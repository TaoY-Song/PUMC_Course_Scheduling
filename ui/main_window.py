#!/usr/bin/env python3
"""
主窗口界面和基础交互逻辑
"""

from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QStyledItemDelegate,
    QCompleter,
)
from PyQt5.QtCore import pyqtSignal, QThread, Qt
from PyQt5.QtGui import QColor, QFont
import os
from pathlib import Path
from typing import List

from core.models import Course, SelectedCourse
from core.data_loader import CourseDataLoader
from core.import_export import SelectedCourseExporter, SelectedCourseImporter
from core.credit_manager import CreditManager
from core.services import get_service_factory
from core.services.course_supplement_service import CourseSupplementService
from core.scheduling.config import (
    SchedulingConfig,
    CreditConstraintMode,
    CampusConflictMode,
)
import ui.dialogs as ui_dialogs


class CategoryComboDelegate(QStyledItemDelegate):
    """自定义类别列的委托，支持组合框编辑"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    def createEditor(self, parent, option, index):
        """创建编辑器"""
        # 获取对应的已选课程
        row = index.row()
        if row >= len(self.main_window.selected_courses):
            return None

        selected_course = self.main_window.selected_courses[row]

        # 创建可编辑的组合框
        combo = QComboBox(parent)
        combo.setEditable(True)

        # 添加预设类别选项
        available_categories = selected_course.get_available_categories()
        combo.addItems(available_categories)

        # 设置自动完成
        completer = QCompleter(available_categories)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(completer)

        return combo

    def setEditorData(self, editor, index):
        """设置编辑器的初始数据"""
        current_text = index.model().data(index, Qt.DisplayRole)
        if isinstance(editor, QComboBox):
            # 设置当前文本
            editor.setCurrentText(current_text)

    def setModelData(self, editor, model, index):
        """将编辑器的数据保存到模型"""
        if isinstance(editor, QComboBox):
            new_category = editor.currentText().strip()

            # 获取对应的已选课程
            row = index.row()
            if row < len(self.main_window.selected_courses):
                selected_course = self.main_window.selected_courses[row]

                # 尝试设置新类别
                if new_category and new_category != "nan":
                    if selected_course.set_custom_category(new_category):
                        model.setData(index, new_category, Qt.DisplayRole)
                        # 更新表格显示样式
                        self.main_window.update_selected_courses_table()
                    else:
                        # 设置失败，恢复原值
                        QMessageBox.warning(self.main_window, "警告", "无法设置该类别")
                else:
                    # 空值或nan，保持原状
                    pass


class CourseLoadThread(QThread):
    """课程加载线程"""

    finished = pyqtSignal(bool, str)  # 成功/失败, 消息
    progress = pyqtSignal(str)  # 进度消息

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.loader = CourseDataLoader()

    def run(self):
        try:
            self.progress.emit("正在加载课程数据...")
            success = self.loader.load_from_excel(self.file_path)

            if success:
                courses = self.loader.get_courses()
                message = f"成功加载 {len(courses)} 门课程"
                self.finished.emit(True, message)
            else:
                self.finished.emit(False, "加载失败")
        except Exception as e:
            self.finished.emit(False, f"加载出错: {str(e)}")


class AlgorithmConfigWidget(QWidget):
    """算法配置组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化算法配置界面"""
        layout = QVBoxLayout()

        # 学分约束模式
        credit_group = QGroupBox("学分约束模式")
        credit_layout = QVBoxLayout()

        self.credit_required_radio = QRadioButton("必需模式 - 严格满足学分要求")
        self.credit_optimal_radio = QRadioButton("优化模式 - 尽量满足学分要求")
        self.credit_optimal_radio.setChecked(True)  # 默认选择优化模式

        # 创建按钮组确保单选行为
        self.credit_button_group = QButtonGroup()
        self.credit_button_group.addButton(self.credit_required_radio)
        self.credit_button_group.addButton(self.credit_optimal_radio)

        credit_layout.addWidget(self.credit_required_radio)
        credit_layout.addWidget(self.credit_optimal_radio)
        credit_group.setLayout(credit_layout)
        layout.addWidget(credit_group)

        # 校区冲突模式
        campus_group = QGroupBox("校区冲突模式")
        campus_layout = QVBoxLayout()

        self.campus_daily_radio = QRadioButton("日内模式 - 同一天不跨校区")
        self.campus_period_radio = QRadioButton("时段模式 - 相邻时段不跨校区")
        self.campus_disabled_radio = QRadioButton("禁用模式 - 允许跨校区")
        self.campus_daily_radio.setChecked(True)  # 默认选择日内模式

        # 创建按钮组确保单选行为
        self.campus_button_group = QButtonGroup()
        self.campus_button_group.addButton(self.campus_daily_radio)
        self.campus_button_group.addButton(self.campus_period_radio)
        self.campus_button_group.addButton(self.campus_disabled_radio)

        campus_layout.addWidget(self.campus_daily_radio)
        campus_layout.addWidget(self.campus_period_radio)
        campus_layout.addWidget(self.campus_disabled_radio)
        campus_group.setLayout(campus_layout)
        layout.addWidget(campus_group)

        self.setLayout(layout)


class AlgorithmControlWidget(QWidget):
    """算法执行控制组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化执行控制界面"""
        layout = QVBoxLayout()

        # 执行按钮
        self.start_scheduling_button = QPushButton("开始智能排课")
        self.start_scheduling_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        layout.addWidget(self.start_scheduling_button)

        # 进度显示
        self.progress_label = QLabel("就绪")
        self.progress_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_label)

        # 状态信息
        self.status_label = QLabel("等待开始排课...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)


class ResultDisplayWidget(QWidget):
    """结果展示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        """初始化结果展示界面"""
        layout = QVBoxLayout()

        # 已选课程列表标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("已选择的课程:"))
        title_layout.addStretch()

        # 课程统计信息
        self.course_count_label = QLabel("共 0 门课程")
        self.course_count_label.setStyleSheet("color: #666666; font-size: 12px;")
        title_layout.addWidget(self.course_count_label)

        layout.addLayout(title_layout)

        # 已选课程表格 (从原来的MainWindow移动过来)
        self.selected_courses_table = QTableWidget()
        self.selected_courses_table.setColumnCount(10)
        self.selected_courses_table.setHorizontalHeaderLabels(
            [
                "课程编码",
                "课程名称",
                "班次",
                "原始类别",
                "设置类别",
                "是否线上",
                "任课教师",
                "校区",
                "学分",
                "时间安排",
            ]
        )
        self.selected_courses_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.selected_courses_table)

        # 操作按钮区域
        button_layout = QHBoxLayout()

        self.add_time_button = QPushButton("添加时间段")
        button_layout.addWidget(self.add_time_button)

        self.remove_course_button = QPushButton("移除课程")
        button_layout.addWidget(self.remove_course_button)

        self.clear_all_button = QPushButton("清空所有")
        button_layout.addWidget(self.clear_all_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)


class ExportFunctionWidget(QWidget):
    """导出功能组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化导出功能界面"""
        layout = QVBoxLayout()

        # 导入导出区域
        import_export_group = QGroupBox("数据管理")
        import_export_layout = QHBoxLayout()

        self.import_button = QPushButton("导入课程")
        self.export_button = QPushButton("导出已选课程")
        self.export_button.setToolTip("导出当前「已选择的课程」表格中显示的原始课程")

        import_export_layout.addWidget(self.import_button)
        import_export_layout.addWidget(self.export_button)
        import_export_group.setLayout(import_export_layout)
        layout.addWidget(import_export_group)

        # 排课结果导出区域
        result_export_group = QGroupBox("智能排课结果")
        result_export_layout = QVBoxLayout()

        self.export_schedule_button = QPushButton("导出排课结果")
        self.export_schedule_button.setEnabled(False)  # 初始禁用，排课完成后启用
        self.export_schedule_button.setToolTip("导出智能排课算法生成的最终排课方案")

        result_export_layout.addWidget(self.export_schedule_button)
        result_export_group.setLayout(result_export_layout)
        layout.addWidget(result_export_group)

        self.setLayout(layout)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.course_loader = None
        self.course_index = {}
        self.selected_courses: List[SelectedCourse] = []  # 用户导入/添加的原始课程
        self.scheduling_result: List[SelectedCourse] = []  # 排课算法的结果
        print("🔍 [调试] MainWindow开始创建CreditManager...")
        self.credit_manager = CreditManager()
        print("🔍 [调试] MainWindow的CreditManager创建完成")

        # 集成服务层
        self.service_factory = get_service_factory()
        self.scheduling_service = self.service_factory.get_scheduling_service(
            self.credit_manager
        )
        self.data_service = self.service_factory.get_data_service()
        self.event_manager = self.service_factory.get_event_manager()

        # 初始化排课配置
        self.scheduling_config = SchedulingConfig()

        self.init_ui()
        self.setWindowTitle("PUMC交互式排课系统")
        self.resize(1200, 800)

        # 初始化服务层集成
        self._init_service_integration()

    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout()

        # 左侧控制面板
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)

        # 右侧显示面板
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 2)

        central_widget.setLayout(main_layout)

    def create_left_panel(self):
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout()

        # 文件加载区域
        file_group = QGroupBox("课程数据加载")
        file_layout = QVBoxLayout()

        self.file_path_label = QLabel("未选择文件")
        file_layout.addWidget(self.file_path_label)

        self.load_file_button = QPushButton("选择Excel文件")
        self.load_file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.load_file_button)

        self.load_status_label = QLabel("")
        file_layout.addWidget(self.load_status_label)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 课程选择区域
        course_group = QGroupBox("课程选择")
        course_layout = QVBoxLayout()

        course_layout.addWidget(QLabel("输入课程编码:"))
        self.course_code_input = QLineEdit()
        self.course_code_input.setPlaceholderText("例如: BIEN01002")
        course_layout.addWidget(self.course_code_input)

        self.search_course_button = QPushButton("查找课程")
        self.search_course_button.clicked.connect(self.search_course)
        self.search_course_button.setEnabled(False)
        course_layout.addWidget(self.search_course_button)

        # 课程信息显示
        self.course_info_text = QTextEdit()
        self.course_info_text.setMaximumHeight(150)
        self.course_info_text.setReadOnly(True)
        course_layout.addWidget(self.course_info_text)

        # 班次选择
        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("选择班次:"))
        self.class_combo = QComboBox()
        self.class_combo.setEnabled(False)
        class_layout.addWidget(self.class_combo)
        course_layout.addLayout(class_layout)

        # 线上课程选择
        self.online_checkbox = QCheckBox("线上课程")
        self.online_checkbox.setToolTip(
            "系统会自动识别线上课程并勾选此选项。\n"
            "如果系统识别错误，您可以手动调整。\n"
            "勾选后该课程将被标记为线上课程。"
        )
        course_layout.addWidget(self.online_checkbox)

        self.add_course_button = QPushButton("添加课程")
        self.add_course_button.clicked.connect(self.add_course)
        self.add_course_button.setEnabled(False)
        course_layout.addWidget(self.add_course_button)

        course_group.setLayout(course_layout)
        layout.addWidget(course_group)

        # 学分统计区域
        credit_group = QGroupBox("学分统计")
        credit_layout = QVBoxLayout()

        # 总体统计
        self.total_credits_label = QLabel("总学分: 0.0/26.0 (0.0%)")
        self.total_credits_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        credit_layout.addWidget(self.total_credits_label)

        # 各类别统计
        self.credit_details_text = QTextEdit()
        self.credit_details_text.setMaximumHeight(150)
        self.credit_details_text.setReadOnly(True)
        credit_layout.addWidget(self.credit_details_text)

        # 学分设置按钮
        credit_button_layout = QHBoxLayout()
        self.credit_settings_button = QPushButton("学分设置")
        self.credit_settings_button.clicked.connect(self.open_credit_settings)
        credit_button_layout.addWidget(self.credit_settings_button)

        self.refresh_credits_button = QPushButton("刷新统计")
        self.refresh_credits_button.clicked.connect(self.update_credit_statistics)
        credit_button_layout.addWidget(self.refresh_credits_button)

        credit_layout.addLayout(credit_button_layout)
        credit_group.setLayout(credit_layout)
        layout.addWidget(credit_group)

        # 课程补充测试区域
        supplement_group = QGroupBox("课程补充测试")
        supplement_layout = QVBoxLayout()

        # 说明文字
        info_label = QLabel("分析排课结果，尝试添加更多可选课程")
        info_label.setStyleSheet("color: #333333; font-size: 16px;")
        supplement_layout.addWidget(info_label)

        # 文件1：排课结果文件
        schedule_file_layout = QHBoxLayout()
        schedule_file_label = QLabel("排课结果文件:")
        schedule_file_label.setStyleSheet(
            "color: #333333; font-size: 18px; min-width: 90px;"
        )
        schedule_file_layout.addWidget(schedule_file_label)

        self.schedule_file_button = QPushButton("选择排课结果.xlsx")
        self.schedule_file_button.clicked.connect(self.select_schedule_file)
        self.schedule_file_button.setToolTip("选择当前的排课结果文件")
        schedule_file_layout.addWidget(self.schedule_file_button)
        supplement_layout.addLayout(schedule_file_layout)

        self.schedule_file_path_label = QLabel("未选择文件")
        self.schedule_file_path_label.setStyleSheet(
            "color: #999999; font-size: 15px; margin-left: 90px;"
        )
        self.schedule_file_path_label.setWordWrap(True)
        supplement_layout.addWidget(self.schedule_file_path_label)

        # 文件2：备选课程表文件
        course_list_layout = QHBoxLayout()
        course_list_label = QLabel("备选课程表:")
        course_list_label.setStyleSheet(
            "color: #333333; font-size: 18px; min-width: 90px;"
        )
        course_list_layout.addWidget(course_list_label)

        self.course_list_button = QPushButton("选择备选课程表.xlsx")
        self.course_list_button.clicked.connect(self.select_course_list_file)
        self.course_list_button.setToolTip("选择可选课程列表文件")
        course_list_layout.addWidget(self.course_list_button)
        supplement_layout.addLayout(course_list_layout)

        self.course_list_path_label = QLabel("未选择文件")
        self.course_list_path_label.setStyleSheet(
            "color: #999999; font-size: 15px; margin-left: 90px;"
        )
        self.course_list_path_label.setWordWrap(True)
        supplement_layout.addWidget(self.course_list_path_label)

        # 开始测试按钮
        self.supplement_button = QPushButton("开始补充测试")
        self.supplement_button.clicked.connect(self.run_course_supplement_test)
        self.supplement_button.setEnabled(False)  # 初始禁用，选择文件后启用
        self.supplement_button.setToolTip("选择两个文件后即可开始测试")
        supplement_layout.addWidget(self.supplement_button)

        self.supplement_status_label = QLabel("请先选择排课结果文件和备选课程表文件")
        self.supplement_status_label.setStyleSheet("color: #666666; font-size: 16px;")
        self.supplement_status_label.setWordWrap(True)
        supplement_layout.addWidget(self.supplement_status_label)

        # 初始化文件路径变量
        self.selected_schedule_file = None
        self.selected_course_list_file = None

        supplement_group.setLayout(supplement_layout)
        layout.addWidget(supplement_group)

        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        """创建右侧算法功能面板"""
        panel = QWidget()
        layout = QVBoxLayout()

        # 1. 算法配置区域 (25%)
        config_group = QGroupBox("排课算法配置")
        config_layout = QVBoxLayout()
        self.algorithm_config_widget = AlgorithmConfigWidget(self)
        config_layout.addWidget(self.algorithm_config_widget)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group, 25)  # 25% 权重

        # 2. 算法执行控制区域 (15%)
        control_group = QGroupBox("执行控制")
        control_layout = QVBoxLayout()
        self.algorithm_control_widget = AlgorithmControlWidget(self)
        control_layout.addWidget(self.algorithm_control_widget)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group, 15)  # 15% 权重

        # 3. 结果展示区域 (45%)
        result_group = QGroupBox("课程管理与结果展示")
        result_layout = QVBoxLayout()
        self.result_display_widget = ResultDisplayWidget(self)
        result_layout.addWidget(self.result_display_widget)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group, 45)  # 45% 权重

        # 4. 导出功能区域 (15%)
        export_group = QGroupBox("导出功能")
        export_layout = QVBoxLayout()
        self.export_function_widget = ExportFunctionWidget(self)
        export_layout.addWidget(self.export_function_widget)
        export_group.setLayout(export_layout)
        layout.addWidget(export_group, 15)  # 15% 权重

        # 连接组件中的信号到MainWindow的方法
        self._connect_widget_signals()

        panel.setLayout(layout)
        return panel

    def _connect_widget_signals(self):
        """连接各组件的信号到MainWindow的方法"""
        # 连接结果展示组件的按钮
        self.result_display_widget.add_time_button.clicked.connect(self.add_time_slot)
        self.result_display_widget.remove_course_button.clicked.connect(
            self.remove_course
        )
        self.result_display_widget.clear_all_button.clicked.connect(
            self.clear_all_courses
        )

        # 连接导出功能组件的按钮
        self.export_function_widget.import_button.clicked.connect(self.import_courses)
        self.export_function_widget.export_button.clicked.connect(self.export_courses)
        self.export_function_widget.export_schedule_button.clicked.connect(
            self.export_scheduling_result
        )
        # 统计报告功能已删除

        # 设置表格的自定义委托
        category_delegate = CategoryComboDelegate(self)
        self.result_display_widget.selected_courses_table.setItemDelegateForColumn(
            4, category_delegate
        )

        # 将结果展示组件的表格设置为MainWindow的属性，保持兼容性
        self.selected_courses_table = self.result_display_widget.selected_courses_table

    def _init_service_integration(self):
        """初始化服务层集成"""
        # 连接算法配置变化事件
        self._connect_algorithm_config_signals()

        # 连接算法执行控制事件
        self.algorithm_control_widget.start_scheduling_button.clicked.connect(
            self._start_scheduling
        )

        # 订阅服务层事件
        self.event_manager.subscribe("scheduling_started", self._on_scheduling_started)
        self.event_manager.subscribe(
            "scheduling_completed", self._on_scheduling_completed
        )
        self.event_manager.subscribe("scheduling_failed", self._on_scheduling_failed)
        self.event_manager.subscribe("ortools_missing", self._on_ortools_missing)

        # 初始化算法配置
        self._update_scheduling_config()

    def _connect_algorithm_config_signals(self):
        """连接算法配置组件的信号"""
        config_widget = self.algorithm_config_widget

        # 学分约束模式变化
        config_widget.credit_required_radio.toggled.connect(self._on_config_changed)
        config_widget.credit_optimal_radio.toggled.connect(self._on_config_changed)

        # 校区冲突模式变化
        config_widget.campus_daily_radio.toggled.connect(self._on_config_changed)
        config_widget.campus_period_radio.toggled.connect(self._on_config_changed)
        config_widget.campus_disabled_radio.toggled.connect(self._on_config_changed)

        # 线上课程统一使用高优先级处理，无需配置信号连接

    def _on_config_changed(self):
        """算法配置变化处理"""
        self._update_scheduling_config()

        # 更新状态显示
        self.algorithm_control_widget.status_label.setText("配置已更新")

    def _update_scheduling_config(self):
        """更新排课配置"""
        config_widget = self.algorithm_config_widget

        # 确定学分约束模式
        if config_widget.credit_required_radio.isChecked():
            credit_mode = CreditConstraintMode.REQUIRED
        else:
            credit_mode = CreditConstraintMode.OPTIMAL

        # 确定校区冲突模式
        if config_widget.campus_daily_radio.isChecked():
            campus_mode = CampusConflictMode.DAILY
        elif config_widget.campus_period_radio.isChecked():
            campus_mode = CampusConflictMode.PERIOD
        else:
            campus_mode = CampusConflictMode.DISABLED

        # 创建新的配置
        self.scheduling_config = SchedulingConfig(
            credit_constraint_mode=credit_mode, campus_conflict_mode=campus_mode
        )

        # 配置服务层
        self.scheduling_service.configure(self.scheduling_config)

    def select_file(self):
        """选择Excel文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择课程一览表", "", "Excel文件 (*.xls *.xlsx)"
        )

        if file_path:
            self.file_path_label.setText(f"文件: {Path(file_path).name}")
            self.load_status_label.setText("正在加载...")

            # 创建加载线程
            self.load_thread = CourseLoadThread(file_path)
            self.load_thread.finished.connect(self.on_load_finished)
            self.load_thread.progress.connect(self.on_load_progress)
            self.load_thread.start()

    def on_load_progress(self, message):
        """加载进度更新"""
        self.load_status_label.setText(message)

    def on_load_finished(self, success, message):
        """加载完成处理"""
        self.load_status_label.setText(message)

        if success:
            self.course_loader = self.load_thread.loader
            self.build_course_index()
            self.search_course_button.setEnabled(True)
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", message)

    def build_course_index(self):
        """建立课程索引"""
        self.course_index = {}
        for course in self.course_loader.get_courses():
            if course.code not in self.course_index:
                self.course_index[course.code] = []
            self.course_index[course.code].append(course)

    def search_course(self):
        """搜索课程"""
        course_code = self.course_code_input.text().strip().upper()

        if not course_code:
            QMessageBox.warning(self, "警告", "请输入课程编码")
            return

        if course_code in self.course_index:
            courses = self.course_index[course_code]
            self.display_course_info(courses)
            self.setup_class_selection(courses)
            self.add_course_button.setEnabled(True)
        else:
            self.course_info_text.setText(f"未找到课程编码: {course_code}")
            self.class_combo.clear()
            self.class_combo.setEnabled(False)
            self.add_course_button.setEnabled(False)

    def display_course_info(self, courses: List[Course]):
        """显示课程信息"""
        if len(courses) == 1:
            course = courses[0]
            info = f"课程名称: {course.name}\n"
            info += f"开课院系: {course.department}\n"
            info += f"任课教师: {course.teacher}\n"
            info += f"校区: {course.campus}\n"
            info += f"学分: {course.credits} | 学时: {course.hours}\n"
            info += f"类别: {course.category}"

            # 添加线上状态信息
            if course.is_online:
                info += "\n📱 线上课程"
            else:
                info += "\n🏫 线下课程"

            # 添加选课说明（如果有）
            if (
                course.description
                and course.description.strip()
                and course.description != "nan"
            ):
                desc = (
                    course.description[:100] + "..."
                    if len(course.description) > 100
                    else course.description
                )
                info += f"\n选课说明: {desc}"

            # 自动设置线上课程复选框状态
            self.online_checkbox.setChecked(course.is_online)
        else:
            info = f"课程名称: {courses[0].name}\n"
            info += f"该课程有 {len(courses)} 个班次\n"
            info += f"类别: {courses[0].category}"

            # 检查多个班次的线上状态是否一致
            online_statuses = [course.is_online for course in courses]
            if all(online_statuses):
                info += "\n📱 所有班次都是线上课程"
                self.online_checkbox.setChecked(True)
            elif any(online_statuses):
                info += "\n⚠️ 部分班次是线上课程，请选择班次后确认"
                self.online_checkbox.setChecked(False)  # 让用户手动选择
            else:
                info += "\n🏫 所有班次都是线下课程"
                self.online_checkbox.setChecked(False)

        self.course_info_text.setText(info)

    def setup_class_selection(self, courses: List[Course]):
        """设置班次选择"""
        self.class_combo.clear()
        self.class_combo.setEnabled(True)

        for course in courses:
            class_info = f"班次{course.class_num} - {course.teacher} ({course.campus})"
            self.class_combo.addItem(class_info, course)

    def add_course(self):
        """添加课程"""
        if self.class_combo.currentData() is None:
            QMessageBox.warning(self, "警告", "请选择班次")
            return

        selected_course_obj = self.class_combo.currentData()

        # 检查是否已经添加过相同的课程编码+班次组合
        for existing in self.selected_courses:
            if (
                existing.course.code == selected_course_obj.code
                and existing.class_num == selected_course_obj.class_num
            ):
                QMessageBox.warning(
                    self,
                    "警告",
                    f"课程 {selected_course_obj.code} 班次{selected_course_obj.class_num} 已经添加过了",
                )
                return

        # 创建选中课程对象
        # 优先使用Course对象的is_online属性，如果用户手动勾选则覆盖
        is_online = selected_course_obj.is_online or self.online_checkbox.isChecked()

        selected_course = SelectedCourse(
            course=selected_course_obj,
            class_num=selected_course_obj.class_num,
            is_online=is_online,
        )

        self.selected_courses.append(selected_course)
        self.update_selected_courses_table()
        self.update_stats()

        # 清空输入
        self.course_code_input.clear()
        self.course_info_text.clear()
        self.class_combo.clear()
        self.class_combo.setEnabled(False)
        self.add_course_button.setEnabled(False)
        self.online_checkbox.setChecked(False)

        QMessageBox.information(self, "成功", f"已添加课程: {selected_course_obj.name}")

    def update_selected_courses_table(self):
        """更新已选课程表格"""
        self.selected_courses_table.setRowCount(len(self.selected_courses))

        for i, selected_course in enumerate(self.selected_courses):
            course = selected_course.course

            # 课程编码
            self.selected_courses_table.setItem(i, 0, QTableWidgetItem(course.code))

            # 课程名称
            self.selected_courses_table.setItem(i, 1, QTableWidgetItem(course.name))

            # 班次
            self.selected_courses_table.setItem(
                i, 2, QTableWidgetItem(str(selected_course.class_num))
            )

            # 原始类别（移除开课院系，原始类别移到第3列）
            self.selected_courses_table.setItem(i, 3, QTableWidgetItem(course.category))

            # 设置类别（移到第4列）
            category_item = QTableWidgetItem(selected_course.custom_category)
            if selected_course.custom_category == "nan":
                category_item.setToolTip("请双击此单元格设置课程类别")
                # 设置红色粗体字体表示需要设置
                category_item.setForeground(QColor("#FF4444"))
                font = QFont()
                font.setBold(True)
                category_item.setFont(font)
            else:
                category_item.setToolTip("双击可以修改课程类别")
                # 设置绿色粗体字体表示可修改
                category_item.setForeground(QColor("#2E8B57"))
                font = QFont()
                font.setBold(True)
                category_item.setFont(font)
            self.selected_courses_table.setItem(i, 4, category_item)

            # 是否线上（新增第5列）
            online_status = "是" if selected_course.is_online else "否"
            online_item = QTableWidgetItem(online_status)
            if selected_course.is_online:
                # 线上课程用蓝色显示
                online_item.setForeground(QColor("#0066CC"))
                font = QFont()
                font.setBold(True)
                online_item.setFont(font)
                online_item.setToolTip("线上课程")
            else:
                # 线下课程用默认颜色
                online_item.setToolTip("线下课程")
            self.selected_courses_table.setItem(i, 5, online_item)

            # 任课教师（保持第6列）
            self.selected_courses_table.setItem(i, 6, QTableWidgetItem(course.teacher))

            # 校区（保持第7列）
            self.selected_courses_table.setItem(i, 7, QTableWidgetItem(course.campus))

            # 学分（保持第8列）
            self.selected_courses_table.setItem(
                i, 8, QTableWidgetItem(str(course.credits))
            )

            # 时间安排 - 显示详细信息
            if selected_course.time_slots:
                if len(selected_course.time_slots) == 1:
                    # 单个时间段，显示详细信息
                    time_info = str(selected_course.time_slots[0])
                else:
                    # 多个时间段，显示数量和简要信息
                    time_info = f"{len(selected_course.time_slots)}个时间段\n"
                    for j, slot in enumerate(
                        selected_course.time_slots[:2]
                    ):  # 最多显示前2个
                        time_info += f"{j + 1}. {slot}\n"
                    if len(selected_course.time_slots) > 2:
                        time_info += "..."
                    time_info = time_info.strip()
            else:
                time_info = "未安排"

            time_item = QTableWidgetItem(time_info)
            time_item.setToolTip(time_info)  # 设置工具提示显示完整信息
            self.selected_courses_table.setItem(i, 9, time_item)

        # 调整列宽
        self.selected_courses_table.resizeColumnsToContents()

    def update_stats(self):
        """更新统计信息"""
        total_courses = len(self.selected_courses)

        # 更新结果展示组件中的课程统计
        self.result_display_widget.course_count_label.setText(
            f"共 {total_courses} 门课程"
        )

        # 更新学分统计
        self.update_credit_statistics()

    def _start_scheduling(self):
        """开始排课"""
        if not self.selected_courses:
            QMessageBox.warning(self, "警告", "请先添加要排课的课程")
            return

        # 重置服务状态（修复：允许重复执行排课）
        try:
            self.scheduling_service.reset()
            print("🔄 服务状态已重置，可以重新执行排课")
        except Exception as e:
            print(f"⚠️  服务状态重置失败: {e}")

        # 更新UI状态
        self.algorithm_control_widget.start_scheduling_button.setEnabled(False)
        self.algorithm_control_widget.progress_label.setText("准备中...")
        self.algorithm_control_widget.status_label.setText("正在启动排课算法...")

        # 执行排课
        self.scheduling_service.execute(self.selected_courses)

        # 所有结果（成功、失败、错误）都通过事件机制处理
        # 这里不需要任何额外处理，避免重复处理

    def _on_scheduling_started(self, event):
        """排课开始事件处理"""
        self.algorithm_control_widget.progress_label.setText("执行中...")
        self.algorithm_control_widget.status_label.setText("排课算法正在运行...")

    def _on_scheduling_completed(self, event):
        """排课完成事件处理"""
        result = event.data.get("result")
        if result:
            self._on_scheduling_completed_internal(result)

    def _on_scheduling_completed_internal(self, result):
        """内部排课完成处理"""
        # 更新UI状态
        self.algorithm_control_widget.start_scheduling_button.setEnabled(True)
        self.algorithm_control_widget.progress_label.setText("完成")

        selected_count = len(result.selected_courses)
        total_score = result.score.total_score
        self.algorithm_control_widget.status_label.setText(
            f"排课完成！选中 {selected_count} 门课程，总分: {total_score:.2f}"
        )

        # 保存排课结果，但不覆盖原始的已选课程列表
        self.scheduling_result = result.selected_courses
        # 注意：不调用 self.update_selected_courses_table()，保持显示原始导入的课程

        # 启用结果导出按钮
        self.export_function_widget.export_schedule_button.setEnabled(True)

        # 显示成功消息
        QMessageBox.information(
            self,
            "排课完成",
            f"智能排课已完成！\n\n"
            f"选中课程: {selected_count} 门\n"
            f"算法评分: {total_score:.2f}\n\n"
            f"排课结果已保存，您可以使用导出功能查看完整的排课结果。\n"
            f"「已选择的课程」表格仍显示您导入的原始课程。",
        )

    def _on_scheduling_failed(self, event):
        """排课失败事件处理"""
        # 避免重复处理：如果UI状态已经是失败状态，不再处理
        if self.algorithm_control_widget.progress_label.text() == "失败":
            return

        error_msg = event.data.get("error", "未知错误")
        self._on_scheduling_failed_internal(Exception(error_msg))

    def _on_ortools_missing(self, event):
        """OR-Tools缺失事件处理"""
        error_msg = event.data.get("error", "OR-Tools导入错误")
        self._on_ortools_missing_error(ImportError(error_msg))

    # 移除重复的分析逻辑 - 现在完全依赖服务层的分析

    # 移除重复的冲突检查方法 - 现在完全依赖服务层的分析

    def _on_scheduling_failed_internal(self, error):
        """内部排课失败处理"""
        # 恢复UI状态
        self.algorithm_control_widget.start_scheduling_button.setEnabled(True)
        self.algorithm_control_widget.progress_label.setText("失败")
        self.algorithm_control_widget.status_label.setText("排课失败")

        # 显示详细错误消息
        QMessageBox.critical(self, "智能排课失败", f"{str(error)}")

    def _on_ortools_missing_error(self, error):
        """OR-Tools缺失错误处理"""
        # 恢复UI状态
        self.algorithm_control_widget.start_scheduling_button.setEnabled(True)
        self.algorithm_control_widget.progress_label.setText("失败")
        self.algorithm_control_widget.status_label.setText("OR-Tools未安装")

        # 显示专门的OR-Tools安装指导
        QMessageBox.critical(
            self,
            "OR-Tools未安装",
            f"排课功能需要OR-Tools库支持，但系统检测到该库未安装。\n\n"
            f"错误详情：\n{str(error)}\n\n"
            f"解决方案：\n"
            f"请在命令行中运行以下命令安装OR-Tools：\n\n"
            f"方法1：pip install ortools\n"
            f"方法2：conda install -c conda-forge ortools\n\n"
            f"安装完成后，请重启程序再试。",
        )

    def update_credit_statistics(self):
        """更新学分统计"""
        print("🔍 [调试] update_credit_statistics 被调用")

        # 添加安全检查
        if not hasattr(self, "credit_manager") or self.credit_manager is None:
            print("⚠️ credit_manager未初始化，跳过学分统计更新")
            return

        try:
            # 🔍 调试：检查当前CreditManager状态
            print("🔍 [调试] 当前CreditManager状态:")
            for category, req in self.credit_manager.requirements.items():
                if req.completed_credits > 0 or req.base_completed_credits > 0:
                    print(
                        f"   📊 {category}: completed={req.completed_credits:.1f}, base={req.base_completed_credits:.1f}"
                    )

            # 更新总体统计
            total_required = self.credit_manager.get_total_required_credits()
            total_completed = self.credit_manager.get_total_completed_credits()
            completion_rate = self.credit_manager.get_overall_completion_rate() * 100
        except Exception as e:
            print(f"❌ 获取学分统计数据失败: {e}")
            return

        self.total_credits_label.setText(
            f"总学分: {total_completed:.1f}/{total_required:.1f} ({completion_rate:.1f}%)"
        )

        # 更新各类别详情
        try:
            details = []
            for summary in self.credit_manager.get_categories_summary():
                category = summary["category"]
                completed = summary["completed"]
                required = summary["required"]
                remaining = summary["remaining"]
                is_completed = summary["is_completed"]

                # 简化类别名称显示
                short_category = category.replace("选修课 - ", "").replace(
                    "公共必修课 - ", ""
                )

                status_icon = "✓" if is_completed else "○"
                if remaining > 0:
                    detail = f"{status_icon} {short_category}: {completed:.1f}/{required:.1f} (未修{remaining:.1f})"
                else:
                    detail = f"{status_icon} {short_category}: {completed:.1f}/{required:.1f} (已完成)"

                details.append(detail)

            self.credit_details_text.setText("\n".join(details))
        except Exception as e:
            print(f"❌ 更新学分类别详情失败: {e}")
            self.credit_details_text.setText("学分统计暂时不可用")

    def open_credit_settings(self):
        """打开学分设置对话框"""
        dialog = ui_dialogs.CreditSettingsDialog(self.credit_manager, self)
        if dialog.exec_() == ui_dialogs.CreditSettingsDialog.Accepted:
            # 设置保存后，刷新统计
            self.update_credit_statistics()

            # 重要修复：重新创建排课服务以使用更新后的CreditManager
            self.scheduling_service = self.service_factory.get_scheduling_service(
                self.credit_manager
            )
            print("🔄 学分设置已更新，排课服务已重新初始化")

    def add_time_slot(self):
        """添加时间段"""
        current_row = self.selected_courses_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择一门课程")
            return

        selected_course = self.selected_courses[current_row]

        # 创建时间段配置对话框（模态）
        dialog = ui_dialogs.TimeSlotDialog(self)

        # 显示对话框并等待结果
        if (
            dialog.exec_() == ui_dialogs.TimeSlotDialog.Accepted
            and dialog.result_time_slot
        ):
            selected_course.time_slots.append(dialog.result_time_slot)
            self.update_selected_courses_table()
            QMessageBox.information(
                self, "成功", f"已添加时间段: {dialog.result_time_slot}"
            )

    def remove_course(self):
        """移除课程"""
        current_row = self.selected_courses_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要移除的课程")
            return

        course_name = self.selected_courses[current_row].course.name
        reply = QMessageBox.question(
            self,
            "确认",
            f"确定要移除课程 '{course_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.selected_courses.pop(current_row)
            self.update_selected_courses_table()
            self.update_stats()

    def clear_all_courses(self):
        """清空所有课程"""
        if not self.selected_courses:
            return

        reply = QMessageBox.question(
            self, "确认", "确定要清空所有已选课程吗？", QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.selected_courses.clear()
            self.update_selected_courses_table()
            self.update_stats()

    def export_courses(self):
        """导出已选课程（原始导入/添加的课程）"""
        if not self.selected_courses:
            QMessageBox.warning(
                self, "警告", "没有已选课程可以导出\n\n请先导入课程或手动添加课程。"
            )
            return

        # 选择保存文件
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出已选课程", "已选课程.xlsx", "Excel文件 (*.xlsx)"
        )

        if file_path:
            exporter = SelectedCourseExporter()
            success = exporter.export_to_excel(self.selected_courses, file_path)

            if success:
                QMessageBox.information(
                    self,
                    "导出成功",
                    f"已成功导出 {len(self.selected_courses)} 门课程！\n\n"
                    f"文件位置: {file_path}\n\n"
                    f"注意：这是您导入/添加的原始课程列表，\n"
                    f"不是智能排课算法的结果。",
                )
            else:
                QMessageBox.critical(self, "导出失败", "导出失败，请检查文件路径和权限")

    def export_scheduling_result(self):
        """导出排课结果"""
        # 检查是否有排课结果
        if not self.scheduling_result:
            QMessageBox.warning(
                self,
                "警告",
                "没有排课结果可以导出\n\n请先执行智能排课算法生成排课方案。",
            )
            return

        # 选择保存文件
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出排课结果", "排课结果.xlsx", "Excel文件 (*.xlsx)"
        )

        if file_path:
            try:
                # 使用数据服务导出排课结果（导出算法生成的结果）
                success = self.data_service.export_selected_courses(
                    self.scheduling_result, file_path
                )

                if success:
                    QMessageBox.information(
                        self,
                        "导出成功",
                        f"排课结果已成功导出！\n\n"
                        f"文件位置: {file_path}\n"
                        f"包含课程: {len(self.scheduling_result)} 门\n\n"
                        f"您可以使用Excel打开查看详细的排课结果。\n"
                        f"注意：这是智能排课算法生成的最终方案。",
                    )
                else:
                    QMessageBox.critical(
                        self, "导出失败", "导出排课结果失败，请检查文件路径和权限"
                    )

            except Exception as e:
                QMessageBox.critical(
                    self, "导出错误", f"导出过程中发生错误：\n{str(e)}"
                )

    def import_courses(self):
        """导入已选课程"""
        # 检查是否已加载课程一览表
        if not self.course_loader:
            QMessageBox.warning(self, "警告", "请先加载课程一览表")
            return

        # 选择导入文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入已选课程", "", "Excel文件 (*.xlsx *.xls)"
        )

        if file_path:
            importer = SelectedCourseImporter()
            imported_courses, report = importer.import_from_excel(
                file_path, self.course_loader
            )

            if report.get("success", False):
                # 询问是否替换现有课程
                if self.selected_courses:
                    reply = QMessageBox.question(
                        self,
                        "确认",
                        f"当前已有 {len(self.selected_courses)} 门课程。\n"
                        f"是否要替换为导入的 {len(imported_courses)} 门课程？",
                        QMessageBox.Yes | QMessageBox.No,
                    )

                    if reply == QMessageBox.No:
                        return

                # 更新已选课程
                self.selected_courses = imported_courses
                self.update_selected_courses_table()
                self.update_stats()

                # 显示导入结果
                success_count = report.get("successful_records", 0)
                failed_count = report.get("failed_records", 0)

                if failed_count > 0:
                    QMessageBox.warning(
                        self,
                        "导入完成",
                        f"导入完成！\n成功: {success_count} 门课程\n失败: {failed_count} 门课程\n\n"
                        f"请检查控制台输出了解失败原因。",
                    )
                else:
                    QMessageBox.information(
                        self, "导入成功", f"成功导入 {success_count} 门课程！"
                    )
            else:
                error_msg = report.get("error", "未知错误")
                QMessageBox.critical(self, "导入失败", f"导入失败: {error_msg}")

    def select_schedule_file(self):
        """选择排课结果文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择排课结果文件", "", "Excel文件 (*.xlsx);;所有文件 (*)"
            )

            if file_path:
                self.selected_schedule_file = file_path
                # 显示文件名（不显示完整路径）
                file_name = os.path.basename(file_path)
                self.schedule_file_path_label.setText(f"已选择: {file_name}")
                self.schedule_file_path_label.setStyleSheet(
                    "color: #2e7d32; font-size: 15px; margin-left: 90px;"
                )

                # 检查是否两个文件都已选择
                self._check_files_ready()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择文件时出错: {str(e)}")

    def select_course_list_file(self):
        """选择备选课程表文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择备选课程表文件", "", "Excel文件 (*.xlsx);;所有文件 (*)"
            )

            if file_path:
                self.selected_course_list_file = file_path
                # 显示文件名（不显示完整路径）
                file_name = os.path.basename(file_path)
                self.course_list_path_label.setText(f"已选择: {file_name}")
                self.course_list_path_label.setStyleSheet(
                    "color: #2e7d32; font-size: 15px; margin-left: 90px;"
                )

                # 检查是否两个文件都已选择
                self._check_files_ready()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择文件时出错: {str(e)}")

    def _check_files_ready(self):
        """检查文件是否都已选择，更新按钮状态"""
        if self.selected_schedule_file and self.selected_course_list_file:
            self.supplement_button.setEnabled(True)
            self.supplement_status_label.setText("文件已准备就绪，可以开始测试")
            self.supplement_status_label.setStyleSheet(
                "color: #2e7d32; font-size: 16px;"
            )
        else:
            self.supplement_button.setEnabled(False)
            missing_files = []
            if not self.selected_schedule_file:
                missing_files.append("排课结果文件")
            if not self.selected_course_list_file:
                missing_files.append("备选课程表文件")
            self.supplement_status_label.setText(
                f"还需要选择: {', '.join(missing_files)}"
            )
            self.supplement_status_label.setStyleSheet(
                "color: #666666; font-size: 16px;"
            )

    def run_course_supplement_test(self):
        """运行课程补充测试"""
        try:
            # 导入对话框类（避免顶层导入冲突）
            from ui.dialogs.supplement_result_dialog import SupplementResultDialog

            # 检查文件是否已选择
            if not self.selected_schedule_file or not self.selected_course_list_file:
                QMessageBox.warning(
                    self, "警告", "请先选择排课结果文件和备选课程表文件"
                )
                return

            # 更新状态
            self.supplement_status_label.setText("正在运行补充测试，请稍候...")
            self.supplement_status_label.setStyleSheet(
                "color: #1976d2; font-size: 16px;"
            )
            self.supplement_button.setEnabled(False)
            self.schedule_file_button.setEnabled(False)
            self.course_list_button.setEnabled(False)

            # 创建服务实例
            service = CourseSupplementService()

            # 运行测试
            result = service.run_supplement_test(
                self.selected_schedule_file, self.selected_course_list_file
            )

            # 显示结果对话框，传递独立日志文件路径
            dialog = SupplementResultDialog(result, service.log_file_path, self)
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"运行课程补充测试时出错:\n{str(e)}\n\n请查看日志文件了解详细信息。",
            )
        finally:
            # 恢复状态
            self._check_files_ready()  # 恢复正确的状态
            self.schedule_file_button.setEnabled(True)
            self.course_list_button.setEnabled(True)
