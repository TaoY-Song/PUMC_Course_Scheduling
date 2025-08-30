"""
服务层模块 - 提供统一的接口层
连接UI、数据加载模块和核心排课算法

这个模块作为中间层，实现：
1. 抽象接口定义
2. 服务层实现
3. 控制器层管理
4. 状态管理和事件通知
"""

from .interfaces import (
    ISchedulingService,
    IDataService,
    IUIController,
    IEventManager,
    SchedulingStatus,
    ServiceEvent,
)

from .scheduling_service import SchedulingService
from .data_service import DataService
from .ui_controller import UIController
from .event_manager import EventManager, get_global_event_manager
from .service_factory import ServiceFactory, get_service_factory

__all__ = [
    "ISchedulingService",
    "IDataService",
    "IUIController",
    "IEventManager",
    "SchedulingStatus",
    "ServiceEvent",
    "SchedulingService",
    "DataService",
    "UIController",
    "EventManager",
    "get_global_event_manager",
    "ServiceFactory",
    "get_service_factory",
]
