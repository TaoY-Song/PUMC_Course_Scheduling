#!/usr/bin/env python3
"""
PUMC交互式排课系统 - Web版本入口

使用方法:
    python app_web.py
"""

import sys
import os
import time
import threading
import webbrowser
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from core.app_paths import default_static_dir, is_frozen, user_data_dir
except (ImportError, ValueError) as _error:
    # pandas/numpy 的 ABI 不匹配会在这里抛 ValueError（不是 ImportError），
    # 直接冒泡出去就是一屏 traceback + 窗口关闭，用户只看到「一打开就闪退」。
    print("❌ 依赖加载失败，程序无法启动。")
    print(f"   原始错误: {type(_error).__name__}: {_error}")
    print()
    print("   常见原因与修复：")
    print("   1) pandas 与 numpy 的二进制版本不匹配")
    print('      （报错含 "numpy.dtype size changed"）')
    print("   2) 依赖装在了另一个 Python 环境里")
    print()
    print("   请在项目目录下重装依赖：")
    print(f"      {sys.executable} -m pip install -r requirements.txt --upgrade")
    sys.exit(1)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="启动PUMC排课系统Web版本")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--host", default="127.0.0.1", help="服务器主机 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口 (默认: 8000)")
    parser.add_argument("--dev", action="store_true", help="开发模式（启用热重载）")
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认 WARNING；DEBUG 会输出排课搜索过程）",
    )
    return parser.parse_args()


def _configure_utf8_output() -> None:
    """避免 Windows 默认 GBK 控制台无法输出中文/符号导致启动失败。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def check_dependencies():
    """检查Web版本所需的依赖是否已安装"""
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI 和 Uvicorn 已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请安装Web版本依赖:")
        print("    pip install -r requirements.txt")
        return False


def start_backend_server(host="127.0.0.1", port=8000):
    """启动FastAPI后端服务器"""
    import uvicorn
    from web_backend.server import app
    
    print(f"🚀 启动后端服务器 http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def open_browser(url: str, delay: int = 2):
    """在指定延迟后打开浏览器"""
    time.sleep(delay)
    print(f"🌐 正在打开浏览器: {url}")
    webbrowser.open(url)


PORT_FALLBACK_TRIES = 20


def check_port_available(host: str, port: int) -> bool:
    """端口当前能否绑定。"""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def port_holders(port: int) -> list:
    """返回监听该端口的 PID 列表；查不到就返回空表。"""
    import subprocess

    if sys.platform == "win32":
        # 原来这里走 `netstat -ano | findstr`，findstr 是 Windows 专有命令，
        # 在 macOS / Linux 上必然失败。改成不依赖 shell 的形式并按平台分流。
        command = ["netstat", "-ano"]
    else:
        command = ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []

    if sys.platform != "win32":
        return [pid for pid in result.stdout.split() if pid.isdigit()]

    # netstat -ano 的列：Proto / 本地地址 / 远端地址 / 状态 / PID
    pids = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[3] != "LISTENING":
            continue
        if not parts[1].endswith(f":{port}"):
            continue
        if parts[4].isdigit() and parts[4] not in pids:
            pids.append(parts[4])
    return pids


def kill_port_holders(port: int) -> bool:
    """终止占用端口的进程；仅 Windows 沿用旧的自动清理行为。"""
    import subprocess

    pids = port_holders(port)
    if not pids:
        return False

    for pid in pids:
        print(f"🔪 正在终止占用端口 {port} 的进程 (PID: {pid})...")
        try:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as error:
            print(f"⚠️  终止进程失败: {error}")
            return False
    time.sleep(1)
    return True


def resolve_port(host: str, port: int) -> int:
    """选出一个能用的端口。

    端口被占用时旧代码只会尝试 Windows 的 taskkill，失败就 ``sys.exit(1)``；
    在 macOS / Linux 上这条路必然走不通，表现就是程序一启动就退出。
    现在改为：Windows 保持自动清理，其余平台顺延到下一个空闲端口。
    """
    if check_port_available(host, port):
        return port

    if sys.platform == "win32" and kill_port_holders(port) and check_port_available(host, port):
        return port

    holders = port_holders(port)
    detail = f"（占用进程 PID: {', '.join(holders)}）" if holders else ""
    print(f"⚠️  端口 {port} 已被占用{detail}")

    for candidate in range(port + 1, port + 1 + PORT_FALLBACK_TRIES):
        if check_port_available(host, candidate):
            print(f"➡️  已自动改用空闲端口 {candidate}（可用 --port 指定其他端口）")
            return candidate

    print(f"❌ {port}-{port + PORT_FALLBACK_TRIES} 全部被占用，请用 --port 指定一个空闲端口")
    sys.exit(1)


def main():
    _configure_utf8_output()
    args = parse_arguments()

    # 日志级别也可通过环境变量 PUMC_LOG_LEVEL 设置
    if args.log_level:
        os.environ["PUMC_LOG_LEVEL"] = args.log_level

    print("=" * 60)
    print("PUMC交互式排课系统 - Web版本")
    print("=" * 60)
    
    if not check_dependencies():
        sys.exit(1)
    
    host = args.host
    # 端口可能因占用而顺延，必须先定下来再打印地址，否则提示的 URL 是错的。
    port = resolve_port(host, args.port)
    url = f"http://{host}:{port}"

    print(f"\n📋 配置信息:")
    print(f"   后端地址: {url}")
    print(f"   API文档:  {url}/docs")
    print(f"   健康检查: {url}/api/health")
    print(f"   开发模式: {'是' if args.dev else '否'}")
    if is_frozen():
        print(f"   数据目录: {user_data_dir()}")
    # 前端未构建/未捐绑时只有 API 可用，提前说清楚比让用户看到白页。
    static_dir = default_static_dir()
    if not (static_dir / "index.html").exists():
        print(f"⚠️  前端产物未找到（{static_dir}），页面将不可用；请先在 web/ 执行 npm run build")
    print()

    if not args.no_browser:
        browser_thread = threading.Thread(
            target=open_browser,
            args=(url, 2),
            daemon=True
        )
        browser_thread.start()
    
    try:
        if args.dev:
            # 冻结包里没有 `-m uvicorn` 入口，也没有源文件可热重载。
            if is_frozen():
                print("⚠️  打包版不支持 --dev 热重载，已改为普通模式启动")
                start_backend_server(host, port)
            else:
                import subprocess
                cmd = [sys.executable, "-m", "uvicorn", 
                       "web_backend.server:app", 
                       "--host", host, 
                       "--port", str(port), 
                       "--reload"]
                subprocess.run(cmd)
        else:
            start_backend_server(host, port)
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 服务器启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
