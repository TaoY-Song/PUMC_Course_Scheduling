"""
事件桥接器
将 Service 层的事件转发到 WebSocket。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.services.interfaces import IEventManager, ServiceEvent

logger = logging.getLogger(__name__)


class WebSocketEventAdapter:
    """WebSocket事件适配器"""
    
    def __init__(self, event_manager: IEventManager):
        self.event_manager = event_manager
        self.handlers: Dict[str, List[Callable]] = {}
        # 🔧 P1 修复：保存事件循环引用。
        # Service 层的事件是从 ThreadPoolExecutor 工作线程发出的，
        # 那里没有运行中的 asyncio loop，asyncio.create_task() 必定抛
        # RuntimeError 并被后面的 except 吞掉，导致 WebSocket 从不推送。
        self._loop: asyncio.AbstractEventLoop | None = None
        self._setup_handlers()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """绑定主事件循环（应在应用启动时从事件循环线程调用）。"""
        self._loop = loop

    def _resolve_loop(self) -> asyncio.AbstractEventLoop | None:
        """获取可用的事件循环。"""
        if self._loop is not None and not self._loop.is_closed():
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None
    
    def _setup_handlers(self):
        """设置事件处理器"""
        self.event_manager.subscribe("scheduling_started", self._on_scheduling_started)
        self.event_manager.subscribe("scheduling_progress", self._on_scheduling_progress)
        self.event_manager.subscribe("scheduling_completed", self._on_scheduling_completed)
        self.event_manager.subscribe("scheduling_failed", self._on_scheduling_failed)
        self.event_manager.subscribe("config_changed", self._on_config_changed)
        # 🔧 P1 修复：核心层实际发出的是 data_loading_completed，
        # 之前订阅的 courses_loaded 从未存在，前端永远收不到该事件。
        self.event_manager.subscribe(
            "data_loading_completed", self._on_courses_loaded
        )
        self.event_manager.subscribe("courses_loaded", self._on_courses_loaded)
    
    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    def unregister_handler(self, event_type: str, handler: Callable):
        """注销事件处理器"""
        if event_type in self.handlers:
            self.handlers[event_type].remove(handler)
    
    def _emit(self, event_type: str, data: Any):
        """触发事件到所有注册的处理器

        🔧 P1 修复：支持跨线程转发。当从非事件循环线程（排课工作线程）
        调用时，使用 run_coroutine_threadsafe 把待办交回主循环；
        同时不再静默吞掉异常，而是输出警告，便于定位问题。
        """
        if event_type not in self.handlers:
            return

        for handler in self.handlers[event_type]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    self._schedule_coroutine(handler(data), event_type)
                else:
                    result = handler(data)
                    # 处理器可能是返回协程的 lambda
                    if asyncio.iscoroutine(result):
                        self._schedule_coroutine(result, event_type)
            except Exception as exc:  # pragma: no cover - 防御性分支
                logger.warning("WebSocket 事件转发失败 [%s]: %s", event_type, exc)

    def _schedule_coroutine(self, coro, event_type: str) -> None:
        """将协程调度到事件循环（线程安全）。"""
        loop = self._resolve_loop()
        if loop is None:
            coro.close()
            logger.warning("WebSocket 事件 [%s] 无法推送：尚未绑定事件循环", event_type)
            return

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is loop:
            loop.create_task(coro)
        else:
            asyncio.run_coroutine_threadsafe(coro, loop)

    def _serialize_value(self, value: Any) -> Any:
        """将复杂对象转换为可 JSON 序列化的数据。"""
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return self._serialize_value(asdict(value))
        if isinstance(value, dict):
            return {
                str(key): self._serialize_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_value(item) for item in value]
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return self._serialize_value(value.to_dict())
        if hasattr(value, "__dict__") and not isinstance(value, type):
            return self._serialize_value(
                {key: val for key, val in vars(value).items() if not key.startswith("_")}
            )
        return value
    
    def _on_scheduling_started(self, event: ServiceEvent):
        """排课开始事件"""
        task_id = event.data.get("task_id")
        if not task_id:
            return
        self._emit("scheduling.started", {
            "task_id": task_id,
            "message": event.data.get("message", "排课任务开始执行"),
            "course_count": event.data.get("course_count", 0),
            "timestamp": event.timestamp
        })
    
    def _on_scheduling_progress(self, event: ServiceEvent):
        """排课进度事件"""
        task_id = event.data.get("task_id")
        if not task_id:
            return
        self._emit("scheduling.progress", {
            "task_id": task_id,
            "message": event.data.get("message", ""),
            "percent": event.data.get("percent"),
            "timestamp": event.timestamp
        })
    
    def _on_scheduling_completed(self, event: ServiceEvent):
        """排课完成事件"""
        task_id = event.data.get("task_id")
        if not task_id:
            return
        self._emit("scheduling.completed", {
            "task_id": task_id,
            "message": event.data.get("message", "排课完成"),
            "result": self._serialize_value(event.data.get("result")),
            "selected_count": event.data.get("selected_count", 0),
            "total_score": event.data.get("total_score", 0),
            "timestamp": event.timestamp
        })
    
    def _on_scheduling_failed(self, event: ServiceEvent):
        """排课失败事件"""
        task_id = event.data.get("task_id")
        if not task_id:
            return
        self._emit("scheduling.failed", {
            "task_id": task_id,
            "error": event.data.get("error", "Unknown error"),
            "timestamp": event.timestamp
        })
    
    def _on_config_changed(self, event: ServiceEvent):
        """配置变更事件"""
        self._emit("config.updated", {
            "config": self._serialize_value(event.data.get("config")),
            "timestamp": event.timestamp
        })
    
    def _on_courses_loaded(self, event: ServiceEvent):
        """课程加载完成事件"""
        self._emit("courses.loaded", {
            "count": event.data.get("count", 0),
            "timestamp": event.timestamp
        })


# 全局适配器实例
_event_adapter: WebSocketEventAdapter = None

def get_event_adapter(event_manager: IEventManager = None) -> WebSocketEventAdapter:
    """获取事件适配器实例"""
    global _event_adapter
    if _event_adapter is None and event_manager is not None:
        _event_adapter = WebSocketEventAdapter(event_manager)
    return _event_adapter
