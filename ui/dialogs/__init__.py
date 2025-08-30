#!/usr/bin/env python3
"""
UI对话框包初始化文件
支持课程补充测试功能和学分设置功能
"""

# 导入课程补充测试结果对话框
from .supplement_result_dialog import SupplementResultDialog


# 使用延迟导入来避免循环导入问题
def _get_dialog_class(class_name):
    """延迟获取对话框类"""
    try:
        import os
        import importlib.util

        # 直接导入dialogs.py文件
        dialogs_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "dialogs.py"
        )
        if os.path.exists(dialogs_path):
            spec = importlib.util.spec_from_file_location(
                "ui_dialogs_module", dialogs_path
            )
            dialogs_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dialogs_module)
            return getattr(dialogs_module, class_name, None)
    except Exception:
        pass
    return None


# 立即获取对话框类
TimeSlotDialog = _get_dialog_class("TimeSlotDialog")
CategorySettingDialog = _get_dialog_class("CategorySettingDialog")
CreditSettingsDialog = _get_dialog_class("CreditSettingsDialog")

__all__ = [
    "TimeSlotDialog",
    "CategorySettingDialog",
    "CreditSettingsDialog",
    "SupplementResultDialog",
]
