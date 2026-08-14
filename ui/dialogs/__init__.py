#!/usr/bin/env python3
"""UI 对话框包

课程/学分相关对话框与补充测试结果对话框的统一入口。

历史问题（已修复）：
之前仓库里同时存在 ``ui/dialogs.py`` 模块和 ``ui/dialogs/`` 包。Python 中包会
遮蔽同名模块，导致：

* ``ui/__init__.py`` 里的 ``from .dialogs import TimeSlotDialog`` 静默失败，
  落进 ``except ImportError`` 分支；
* 本文件只能用 ``importlib.util.spec_from_file_location`` 手动加载
  ``dialogs.py``，把同一批类在 ``ui_dialogs_module`` 这个假模块名下**重复加载一次**，
  于是 ``isinstance`` / ``except`` 之类基于类身份的判断会失效；
* 加载失败时被 ``except Exception: pass`` 吞掉，对话框会变成 ``None``，
  真正报错要等到用户点开对话框才出现。

现在 ``dialogs.py`` 已并入本包，成为常规子模块 ``course_dialogs``，
不再有动态加载和名字遮蔽。
"""

from .course_dialogs import (
    CategorySettingDialog,
    CreditSettingsDialog,
    TimeSlotDialog,
)
from .supplement_result_dialog import SupplementResultDialog

__all__ = [
    "TimeSlotDialog",
    "CategorySettingDialog",
    "CreditSettingsDialog",
    "SupplementResultDialog",
]
