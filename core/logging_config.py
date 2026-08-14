"""集中式日志配置

项目原先在核心逻辑里散落了 160 多个 ``print()``，其中排课回溯算法的热路径
每递归一步就打印数行。这有两个后果：

1. 正常使用时终端被调试信息淹没，真正的警告被埋掉；
2. 回溯搜索本身被 I/O 拖慢——打印的开销与搜索空间同阶增长。

这里提供一个统一的 logger 工厂，默认只输出 WARNING 及以上，可通过环境变量
``PUMC_LOG_LEVEL`` 调整（例如 ``DEBUG`` 用于排查排课过程）。

用法::

    from core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.debug("详细的搜索过程")
    logger.info("阶段性结果")
    logger.warning("需要用户注意的问题")
"""

from __future__ import annotations

import logging
import os
import sys

_DEFAULT_LEVEL = "WARNING"
_ENV_VAR = "PUMC_LOG_LEVEL"
_configured = False


def _resolve_level() -> int:
    raw = os.environ.get(_ENV_VAR, _DEFAULT_LEVEL).strip().upper()
    return getattr(logging, raw, logging.WARNING)


def configure_logging(force: bool = False) -> None:
    """初始化根 logger（幂等）。"""
    global _configured
    if _configured and not force:
        return

    root = logging.getLogger("pumc")
    root.setLevel(_resolve_level())

    # 避免重复添加 handler（例如 Qt 版和 Web 版在同进程内都初始化过）
    if not root.handlers or force:
        root.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)

    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取带 ``pumc.`` 前缀的 logger。"""
    configure_logging()
    suffix = name.split(".")[-1] if name else "core"
    return logging.getLogger(f"pumc.{suffix}")
