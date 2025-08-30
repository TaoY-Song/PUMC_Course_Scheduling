"""
UI控制器实现 - 管理UI和服务层之间的交互

这个模块提供了UI控制器的基础实现，可以被具体的UI组件继承使用。
"""

from typing import List, Callable, Dict
import logging

from .interfaces import IUIController, ServiceEvent
from ..models import SelectedCourse
from ..scheduling.config import SchedulingConfig
from ..scheduling.models import ScheduleResult


class UIController(IUIController):
    """UI控制器基础实现类"""

    def __init__(self, event_manager=None):
        """初始化UI控制器"""
        self._event_manager = event_manager
        self._event_handlers: Dict[str, List[Callable[[ServiceEvent], None]]] = {}
        self._logger = logging.getLogger(__name__)

        # 注册默认事件处理器
        if self._event_manager:
            self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """注册默认事件处理器"""
        # 排课相关事件
        self._event_manager.subscribe("scheduling_started", self._on_scheduling_started)
        self._event_manager.subscribe(
            "scheduling_completed", self._on_scheduling_completed
        )
        self._event_manager.subscribe("scheduling_failed", self._on_scheduling_failed)
        self._event_manager.subscribe(
            "scheduling_cancelled", self._on_scheduling_cancelled
        )

        # 数据相关事件
        self._event_manager.subscribe(
            "data_loading_started", self._on_data_loading_started
        )
        self._event_manager.subscribe(
            "data_loading_completed", self._on_data_loading_completed
        )
        self._event_manager.subscribe(
            "data_loading_failed", self._on_data_loading_failed
        )

        # 配置相关事件
        self._event_manager.subscribe("config_changed", self._on_config_changed)

    def on_algorithm_config_changed(self, config: SchedulingConfig) -> None:
        """算法配置变化回调 - 子类应重写此方法"""
        self._logger.debug(f"算法配置变化: {config}")

    def on_scheduling_requested(self, courses: List[SelectedCourse]) -> None:
        """排课请求回调 - 子类应重写此方法"""
        self._logger.debug(f"排课请求: {len(courses)} 门课程")

    def on_scheduling_progress(self, progress: float, message: str) -> None:
        """排课进度回调 - 子类应重写此方法"""
        self._logger.debug(f"排课进度: {progress:.1%} - {message}")

    def on_scheduling_completed(self, result: ScheduleResult) -> None:
        """排课完成回调 - 子类应重写此方法"""
        self._logger.debug(f"排课完成: 选中 {len(result.selected_courses)} 门课程")

    def on_scheduling_failed(self, error: Exception) -> None:
        """排课失败回调 - 子类应重写此方法"""
        self._logger.error(f"排课失败: {error}")

    def register_event_handler(
        self, event_type: str, handler: Callable[[ServiceEvent], None]
    ) -> None:
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []

        self._event_handlers[event_type].append(handler)

        # 如果有事件管理器，也注册到全局事件管理器
        if self._event_manager:
            self._event_manager.subscribe(event_type, handler)

    # 默认事件处理器实现
    def _on_scheduling_started(self, event: ServiceEvent) -> None:
        """处理排课开始事件"""
        self.on_scheduling_progress(0.0, "开始排课...")

    def _on_scheduling_completed(self, event: ServiceEvent) -> None:
        """处理排课完成事件"""
        result = event.data.get("result")
        if result:
            self.on_scheduling_completed(result)

    def _on_scheduling_failed(self, event: ServiceEvent) -> None:
        """处理排课失败事件"""
        error_msg = event.data.get("error", "未知错误")
        self.on_scheduling_failed(Exception(error_msg))

    def _on_scheduling_cancelled(self, event: ServiceEvent) -> None:
        """处理排课取消事件"""
        self.on_scheduling_progress(0.0, "排课已取消")

    def _on_data_loading_started(self, event: ServiceEvent) -> None:
        """处理数据加载开始事件"""
        operation = event.data.get("operation", "数据操作")
        self._logger.debug(f"开始{operation}")

    def _on_data_loading_completed(self, event: ServiceEvent) -> None:
        """处理数据加载完成事件"""
        operation = event.data.get("operation", "数据操作")
        self._logger.debug(f"{operation}完成")

    def _on_data_loading_failed(self, event: ServiceEvent) -> None:
        """处理数据加载失败事件"""
        operation = event.data.get("operation", "数据操作")
        error = event.data.get("error", "未知错误")
        self._logger.error(f"{operation}失败: {error}")

    def _on_config_changed(self, event: ServiceEvent) -> None:
        """处理配置变化事件"""
        config = event.data.get("config")
        if config:
            self.on_algorithm_config_changed(config)
