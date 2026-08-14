"""打包（冻结）后的路径解析回归测试。

这些断言锁定的是「exe 里会坏、源码里看不出来」的那类问题：
相对路径随 CWD 漂移、往只读安装目录写文件、捆绑资源找不到。
"""

import sys
from pathlib import Path

import pytest

from core import app_paths


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """伪造 PyInstaller 环境：sys.frozen + sys._MEIPASS + 独立数据目录。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setenv("PUMC_DATA_DIR", str(tmp_path / "userdata"))
    return tmp_path


def test_source_mode_keeps_paths_inside_the_project():
    """开发工作流不能被改动：源码运行时仍写项目目录。"""
    project_root = Path(__file__).resolve().parent.parent

    assert app_paths.is_frozen() is False
    assert app_paths.default_static_dir() == project_root / "web" / "dist"
    assert app_paths.default_artifacts_dir() == project_root / "exports"
    assert app_paths.default_log_path("app.log") == project_root / "app.log"


def test_frozen_resources_resolve_into_the_bundle(frozen):
    """捆绑资源必须来自 _MEIPASS，而不是 __file__ 旁边。"""
    bundle = frozen / "bundle"

    assert app_paths.resource_root() == bundle
    assert app_paths.default_static_dir() == bundle / "web" / "dist"
    assert app_paths.resource_path("PUMClogo.ico") == bundle / "PUMClogo.ico"


def test_frozen_writable_dirs_leave_the_program_directory(frozen):
    """导出/上传/日志不能落在 _MEIPASS（退出即删）或安装目录（只读）。"""
    bundle = frozen / "bundle"
    writable = [
        app_paths.default_artifacts_dir(),
        app_paths.default_upload_temp_dir(),
        app_paths.default_log_path("app.log"),
    ]

    for path in writable:
        assert bundle not in path.parents, path
        assert app_paths.user_data_dir() in path.parents, path


def test_user_data_dir_is_created_and_writable(frozen):
    directory = app_paths.user_data_dir()

    assert directory.is_dir()
    probe = directory / "write-probe.txt"
    probe.write_text("ok", encoding="utf-8")
    assert probe.read_text(encoding="utf-8") == "ok"


def test_settings_defaults_are_absolute():
    """相对路径会随当前工作目录漂移，双击启动时解析到桌面等位置。"""
    from web_backend.config import WebBackendSettings

    settings = WebBackendSettings()

    assert Path(settings.static_dir).is_absolute()
    assert Path(settings.upload_temp_dir).is_absolute()


def test_spa_is_served_regardless_of_working_directory(monkeypatch, tmp_path):
    """静态目录曾按 CWD 解析，用户双击 exe 时页面 404、只剩 API。"""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    monkeypatch.chdir(tmp_path)  # 任何不是项目根的目录
    from web_backend.server import app

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
