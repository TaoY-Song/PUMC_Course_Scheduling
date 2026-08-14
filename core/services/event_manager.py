"""
事件管理器实现 - 提供事件发布订阅机制

这个模块实现了观察者模式，用于组件间的松耦合通信。
"""

from typing import Dict, List, Callable
from threading import Lock
import logging

from .interfaces import IEventManager, ServiceEvent


class EventManager(IEventManager):
    """事件管理器实现类"""

    def __init__(self):
        """初始化事件管理器"""
        self._handlers: Dict[str, List[Callable[[ServiceEvent], None]]] = {}
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)

    def emit(self, event: ServiceEvent) -> None:
        """发送事件；复制订阅列表后再调用，允许处理器安全地重入。"""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        self._logger.debug(f"发送事件: {event.event_type} from {event.source}")
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.error(f"事件处理器执行失败: {e}")

    def subscribe(
        self, event_type: str, handler: Callable[[ServiceEvent], None]
    ) -> None:
        """订阅事件"""
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []

            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                self._logger.debug(f"订阅事件: {event_type}")

    def unsubscribe(
        self, event_type: str, handler: Callable[[ServiceEvent], None]
    ) -> None:
        """取消订阅"""
        with self._lock:
            if event_type in self._handlers:
                if handler in self._handlers[event_type]:
                    self._handlers[event_type].remove(handler)
                    self._logger.debug(f"取消订阅事件: {event_type}")

                # 如果没有订阅者了，删除事件类型
                if not self._handlers[event_type]:
                    del self._handlers[event_type]

    def get_event_types(self) -> List[str]:
        """获取所有已订阅的事件类型"""
        with self._lock:
            return list(self._handlers.keys())

    def get_handler_count(self, event_type: str) -> int:
        """获取指定事件类型的处理器数量"""
        with self._lock:
            return len(self._handlers.get(event_type, []))

    def clear_all(self) -> None:
        """清除所有订阅"""
        with self._lock:
            self._handlers.clear()
            self._logger.debug("清除所有事件订阅")


# 全局事件管理器实例
_global_event_manager = None


def get_global_event_manager() -> EventManager:
    """获取全局事件管理器实例"""
    global _global_event_manager
    if _global_event_manager is None:
        _global_event_manager = EventManager()
    return _global_event_manager
