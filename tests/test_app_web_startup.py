"""端口占用时的启动行为。

旧实现只会尝试 Windows 的 `netstat | findstr` + `taskkill`，在 macOS / Linux
上那条路必然失败，然后 `sys.exit(1)` —— 用户看到的就是「一打开就闪退」。
"""

import socket
import sys

import pytest

import app_web


@pytest.fixture
def occupied_port():
    """占住一个端口，并把端口号交给用例。"""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    try:
        yield holder.getsockname()[1]
    finally:
        holder.close()


def test_free_port_is_reported_available():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    assert app_web.check_port_available("127.0.0.1", port) is True


def test_occupied_port_is_reported_unavailable(occupied_port):
    assert app_web.check_port_available("127.0.0.1", occupied_port) is False


def test_resolve_port_falls_back_instead_of_exiting(occupied_port):
    """核心回归：端口被占用不该让进程退出。"""
    resolved = app_web.resolve_port("127.0.0.1", occupied_port)

    assert resolved != occupied_port
    assert app_web.check_port_available("127.0.0.1", resolved)


def test_resolve_port_keeps_a_free_port_untouched():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    assert app_web.resolve_port("127.0.0.1", port) == port


def test_resolve_port_exits_when_the_whole_range_is_taken(monkeypatch, occupied_port):
    monkeypatch.setattr(app_web, "check_port_available", lambda host, port: False)
    monkeypatch.setattr(app_web, "port_holders", lambda port: [])

    with pytest.raises(SystemExit) as excinfo:
        app_web.resolve_port("127.0.0.1", occupied_port)

    assert excinfo.value.code == 1


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX 专有：验证不再调用 findstr")
def test_port_holders_uses_lsof_on_posix(monkeypatch, occupied_port):
    recorded = {}

    import subprocess

    def fake_run(command, **kwargs):
        recorded["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="4242\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert app_web.port_holders(occupied_port) == ["4242"]
    assert recorded["command"][0] == "lsof"
    assert "findstr" not in " ".join(recorded["command"])


def test_port_holders_survives_a_missing_tool(monkeypatch, occupied_port):
    import subprocess

    def boom(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", boom)

    assert app_web.port_holders(occupied_port) == []
