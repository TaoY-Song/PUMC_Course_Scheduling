"""运行位置无关的路径解析。

源码运行时一切都在项目目录里，所以到处用相对路径也能跑。但打包成
exe 后有两个变化会让这些路径失效：

1. 当前工作目录不再是项目目录。用户双击图标时 CWD 可能是桌面，
   ``"./web/dist"`` 这类相对路径会解析到错误位置。
2. 程序目录可能只读（``C:\\Program Files\\...``），onefile 模式下
   甚至是退出即删的临时解包目录。往那里写导出文件会失败或丢数据。

因此把路径分成两类，分别从这里取：

* **资源**（前端产物、图标）：只读，随程序分发，用 :func:`resource_path`。
* **用户数据**（导出、上传缓存、日志）：可写，跨版本保留，用
  :func:`user_data_dir` 及其派生函数。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "PUMC_Course_Scheduling"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 等冻结包中。"""
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """只读资源根目录。

    PyInstaller onefile 会把捆绑数据解压到 ``sys._MEIPASS``；onedir 则
    放在可执行文件旁边。源码运行时是项目根目录。
    """
    if is_frozen():
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            return Path(bundle_dir)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """拼出捆绑资源的绝对路径。"""
    return resource_root().joinpath(*parts)


def user_data_dir() -> Path:
    """可写的用户数据目录（按平台惯例，必要时创建）。

    ``PUMC_DATA_DIR`` 可覆盖，便于测试和便携部署。
    """
    override = os.environ.get("PUMC_DATA_DIR")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = (Path(root) if root else Path.home() / "AppData" / "Local") / APP_DIR_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        root = os.environ.get("XDG_DATA_HOME")
        base = (Path(root) if root else Path.home() / ".local" / "share") / APP_DIR_NAME

    base.mkdir(parents=True, exist_ok=True)
    return base


def _writable_subdir(name: str) -> Path:
    """开发时留在项目目录，打包后落到用户数据目录。

    源码运行保持原路径，避免既有工作流（``exports/`` 里找文件、
    仓库内的相对路径）在开发期被改掉。
    """
    if is_frozen():
        return user_data_dir() / name
    return Path(__file__).resolve().parent.parent / name


def default_static_dir() -> Path:
    """前端构建产物目录（``web/dist``）。"""
    return resource_path("web", "dist")


def default_artifacts_dir() -> Path:
    """导出文件与运行工件目录。"""
    return _writable_subdir("exports")


def default_upload_temp_dir() -> Path:
    """上传临时目录。"""
    return _writable_subdir("temp") / "uploads"


def default_log_path(file_name: str) -> Path:
    """日志文件路径；打包后写用户数据目录，避免只读安装位置。"""
    if is_frozen():
        return user_data_dir() / file_name
    return Path(__file__).resolve().parent.parent / file_name
