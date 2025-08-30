#!/usr/bin/env python3
"""
PUMC交互式排课系统 - 应用程序入口
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


class LogManager:
    """日志管理器，负责将输出同时写入文件和控制台"""

    def __init__(self, file_path):
        self.file_path = file_path
        try:
            # 每次运行时覆盖原有日志文件
            self.log_file = open(file_path, "w", encoding="utf-8")
            # 写入时间戳标记
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_file.write(f"=== 智能排课系统运行日志 - {timestamp} ===\n")
            self.log_file.flush()
            print(f"📝 日志记录已启用，日志文件：{file_path}")
        except Exception as e:
            print(f"⚠️ 警告：无法创建日志文件 {file_path}: {e}")
            self.log_file = None

    def write(self, text):
        """写入文本到日志文件"""
        if self.log_file:
            try:
                self.log_file.write(text)
                self.log_file.flush()  # 立即刷新到文件
            except Exception:
                pass  # 忽略文件写入错误，不影响程序运行

    def close(self):
        """关闭日志文件"""
        if self.log_file:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.log_file.write(f"\n=== 程序结束 - {timestamp} ===\n")
                self.log_file.close()
            except Exception:
                pass


class TeeOutput:
    """双向输出类，同时输出到控制台和日志文件"""

    def __init__(self, original_stream, log_manager):
        self.original_stream = original_stream
        self.log_manager = log_manager

    def write(self, text):
        """写入文本到控制台和日志文件"""
        # 写入控制台（如果可用）
        if self.original_stream and hasattr(self.original_stream, "write"):
            try:
                self.original_stream.write(text)
            except Exception:
                pass  # 在打包环境中可能无法写入控制台

        # 写入日志文件
        if self.log_manager:
            self.log_manager.write(text)

    def flush(self):
        """刷新输出流"""
        if self.original_stream and hasattr(self.original_stream, "flush"):
            try:
                self.original_stream.flush()
            except Exception:
                pass  # 在打包环境中可能无法刷新控制台


def main():
    """主函数"""
    # 保存原始输出流
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # 创建日志文件路径（在项目根目录下）
    log_file_path = os.path.join(os.path.dirname(__file__), "app.log")

    # 创建日志管理器
    log_manager = LogManager(log_file_path)

    # 创建双向输出对象
    tee_stdout = TeeOutput(original_stdout, log_manager)
    tee_stderr = TeeOutput(original_stderr, log_manager)

    try:
        # 重定向标准输出和错误输出到日志文件
        sys.stdout = tee_stdout
        sys.stderr = tee_stderr

        # 创建Qt应用程序
        app = QApplication(sys.argv)

        # 设置应用程序信息
        app.setApplicationName("PUMC交互式排课系统")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("PUMC")

        # 创建主窗口
        window = MainWindow()
        window.show()

        # 运行应用程序
        sys.exit(app.exec_())

    finally:
        # 恢复原始输出流
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        # 关闭日志文件
        log_manager.close()


if __name__ == "__main__":
    main()
