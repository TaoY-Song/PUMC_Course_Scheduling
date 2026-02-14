"""
FastAPI依赖注入容器
通过复用现有的ServiceFactory实现依赖注入
"""
from typing import Generator
from fastapi import Request

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services import get_service_factory
from core.services.interfaces import (
    ISchedulingService,
    IDataService,
    IEventManager
)

_service_factory = get_service_factory()


def get_scheduling_service() -> Generator[ISchedulingService, None, None]:
    """获取排课服务实例"""
    yield _service_factory.get_scheduling_service()


def get_data_service() -> Generator[IDataService, None, None]:
    """获取数据服务实例"""
    yield _service_factory.get_data_service()


def get_event_manager() -> Generator[IEventManager, None, None]:
    """获取事件管理器实例"""
    yield _service_factory.get_event_manager()
