"""
FastAPI 依赖注入容器。

Web 版本的所有路由统一依赖 `WebSessionContext`，避免课程、学分和排课结果
分别维护不同的内存副本。
"""

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.interfaces import IDataService, IEventManager, ISchedulingService

from .state import WebSessionContext, get_web_session_context


def get_web_session() -> WebSessionContext:
    """获取 Web 会话上下文单例。"""
    return get_web_session_context()


def get_scheduling_service() -> ISchedulingService:
    """获取排课服务实例。"""
    return get_web_session_context().scheduling_service


def get_data_service() -> IDataService:
    """获取数据服务实例。"""
    return get_web_session_context().data_service


def get_event_manager() -> IEventManager:
    """获取事件管理器实例。"""
    return get_web_session_context().event_manager
