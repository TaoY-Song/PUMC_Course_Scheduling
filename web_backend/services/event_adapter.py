"""
事件桥接器
将 Service 层的事件转发到 WebSocket。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.services.interfaces import IEventManager, ServiceEvent


class WebSocketEventAdapter:
    """WebSocket事件适配器"""
    
    def __init__(self, event_manager: IEventManager):
        self.event_manager = event_manager
        self.handlers: Dict[str, List[Callable]] = {}
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置事件处理器"""
        self.event_manager.subscribe("scheduling_started", self._on_scheduling_started)
        self.event_manager.subscribe("scheduling_progress", self._on_scheduling_progress)
        self.event_manager.subscribe("scheduling_completed", self._on_scheduling_completed)
        self.event_manager.subscribe("scheduling_failed", self._on_scheduling_failed)
        self.event_manager.subscribe("config_changed", self._on_config_changed)
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
        """触发事件到所有注册的处理器"""
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(data))
                    else:
                        handler(data)
                except Exception:
                    pass

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
        self._emit("scheduling.started", {
            "course_count": event.data.get("course_count", 0),
            "timestamp": event.timestamp
        })
    
    def _on_scheduling_progress(self, event: ServiceEvent):
        """排课进度事件"""
        self._emit("scheduling.progress", {
            "message": event.data.get("message", ""),
            "percent": event.data.get("percent"),
            "timestamp": event.timestamp
        })
    
    def _on_scheduling_completed(self, event: ServiceEvent):
        """排课完成事件"""
        self._emit("scheduling.completed", {
            "result": self._serialize_value(event.data.get("result")),
            "selected_count": event.data.get("selected_count", 0),
            "total_score": event.data.get("total_score", 0),
            "timestamp": event.timestamp
        })
    
    def _on_scheduling_failed(self, event: ServiceEvent):
        """排课失败事件"""
        self._emit("scheduling.failed", {
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
