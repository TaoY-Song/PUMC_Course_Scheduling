"""
界面层模块
"""

from .dialogs import (
    CategorySettingDialog,
    CreditSettingsDialog,
    SupplementResultDialog,
    TimeSlotDialog,
)
from .main_window import MainWindow

# 之前这里用 try/except ImportError 包住对话框导入，而 ui/dialogs.py 被
# 同名的 ui/dialogs/ 包遮蔽后导入必然失败，异常被吞掉，__all__ 静默退化成
# 只有 MainWindow。dialogs.py 并入包之后导入是确定成功的，不再需要兜底。
__all__ = [
    "MainWindow",
    "TimeSlotDialog",
    "CategorySettingDialog",
    "CreditSettingsDialog",
    "SupplementResultDialog",
]
