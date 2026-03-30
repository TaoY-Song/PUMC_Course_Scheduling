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


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="启动PUMC排课系统Web版本")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--host", default="127.0.0.1", help="服务器主机 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口 (默认: 8000)")
    parser.add_argument("--dev", action="store_true", help="开发模式（启用热重载）")
    return parser.parse_args()


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


def check_port_available(host: str, port: int, force_kill: bool = False) -> bool:
    """检查端口是否可用，如被占用可选择强制杀掉"""
    import socket
    import subprocess
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        if force_kill:
            try:
                result = subprocess.run(
                    f'netstat -ano | findstr :{port}',
                    shell=True, capture_output=True, text=True
                )
                for line in result.stdout.strip().split('\n'):
                    if 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            print(f"🔪 正在终止占用端口 {port} 的进程 (PID: {pid})...")
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                            time.sleep(1)
                            return check_port_available(host, port, force_kill=False)
            except Exception as e:
                print(f"⚠️  终止进程失败: {e}")
        return False


def main():
    args = parse_arguments()
    
    print("=" * 60)
    print("PUMC交互式排课系统 - Web版本")
    print("=" * 60)
    
    if not check_dependencies():
        sys.exit(1)
    
    host = args.host
    port = args.port
    url = f"http://{host}:{port}"
    
    print(f"\n📋 配置信息:")
    print(f"   后端地址: {url}")
    print(f"   API文档:  {url}/docs")
    print(f"   健康检查: {url}/api/health")
    print(f"   开发模式: {'是' if args.dev else '否'}")
    print()
    
    # 检查端口是否被占用，如被占用则自动杀掉进程
    if not check_port_available(host, port, force_kill=True):
        print(f"⚠️  无法启动服务器，端口 {port} 被占用且无法终止")
        sys.exit(1)
    
    if not args.no_browser:
        browser_thread = threading.Thread(
            target=open_browser,
            args=(url, 2),
            daemon=True
        )
        browser_thread.start()
    
    try:
        if args.dev:
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
