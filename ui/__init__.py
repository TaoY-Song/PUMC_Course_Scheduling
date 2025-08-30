"""
界面层模块
"""

from .main_window import MainWindow

# 直接从dialogs.py文件导入对话框类，避免包导入问题
try:
    from .dialogs import TimeSlotDialog, CategorySettingDialog, CreditSettingsDialog

    __all__ = [
        "MainWindow",
        "TimeSlotDialog",
        "CategorySettingDialog",
        "CreditSettingsDialog",
    ]
except ImportError:
    # 如果导入失败，只导出MainWindow
    __all__ = ["MainWindow"]
