"""
服务工厂 - 提供服务实例的创建和管理

这个模块实现了工厂模式，用于创建和管理各种服务实例。
"""

from typing import Optional

from .interfaces import ISchedulingService, IDataService, IUIController, IEventManager
from .scheduling_service import SchedulingService
from .data_service import DataService
from .ui_controller import UIController
from .event_manager import EventManager, get_global_event_manager


class ServiceFactory:
    """服务工厂类"""

    def __init__(self, use_global_event_manager: bool = True):
        """初始化服务工厂"""
        self._event_manager = (
            get_global_event_manager() if use_global_event_manager else EventManager()
        )
        self._scheduling_service: Optional[ISchedulingService] = None
        self._data_service: Optional[IDataService] = None
        self._ui_controller: Optional[IUIController] = None

    def get_event_manager(self) -> IEventManager:
        """获取事件管理器"""
        return self._event_manager

    def get_scheduling_service(self, credit_manager=None) -> ISchedulingService:
        """获取排课服务实例（单例）"""
        if self._scheduling_service is None or credit_manager is not None:
            # 如果传入了新的credit_manager，重新创建服务实例
            self._scheduling_service = SchedulingService(
                self._event_manager, credit_manager
            )
        return self._scheduling_service

    def get_data_service(self) -> IDataService:
        """获取数据服务实例（单例）"""
        if self._data_service is None:
            self._data_service = DataService(self._event_manager)
        return self._data_service

    def get_ui_controller(self) -> IUIController:
        """获取UI控制器实例（单例）"""
        if self._ui_controller is None:
            self._ui_controller = UIController(self._event_manager)
        return self._ui_controller

    def create_scheduling_service(self) -> ISchedulingService:
        """创建新的排课服务实例"""
        return SchedulingService(self._event_manager)

    def create_data_service(self) -> IDataService:
        """创建新的数据服务实例"""
        return DataService(self._event_manager)

    def create_ui_controller(self) -> IUIController:
        """创建新的UI控制器实例"""
        return UIController(self._event_manager)

    def reset_all_services(self) -> None:
        """重置所有服务实例"""
        self._scheduling_service = None
        self._data_service = None
        self._ui_controller = None

        # 清除事件管理器的所有订阅
        if hasattr(self._event_manager, "clear_all"):
            self._event_manager.clear_all()


# 全局服务工厂实例
_global_service_factory = None


def get_service_factory() -> ServiceFactory:
    """获取全局服务工厂实例"""
    global _global_service_factory
    if _global_service_factory is None:
        _global_service_factory = ServiceFactory()
    return _global_service_factory
