"""
接口定义模块 - 定义服务层的抽象接口

这个模块定义了系统各层之间的标准接口，确保模块间的松耦合。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass

from ..models import Course, SelectedCourse
from ..scheduling.config import SchedulingConfig
from ..scheduling.models import ScheduleResult


class SchedulingStatus(Enum):
    """排课状态枚举"""

    IDLE = "idle"  # 空闲状态
    CONFIGURING = "configuring"  # 配置中
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 取消


@dataclass
class ServiceEvent:
    """服务事件数据类"""

    event_type: str  # 事件类型
    data: Dict[str, Any]  # 事件数据
    timestamp: float  # 时间戳
    source: str  # 事件源


class ISchedulingService(ABC):
    """排课服务接口"""

    @abstractmethod
    def configure(self, config: SchedulingConfig) -> None:
        """配置排课参数"""
        pass

    @abstractmethod
    def execute(self, courses: List[SelectedCourse]) -> ScheduleResult:
        """执行排课算法"""
        pass

    @abstractmethod
    def get_status(self) -> SchedulingStatus:
        """获取当前状态"""
        pass

    @abstractmethod
    def cancel(self) -> bool:
        """取消执行"""
        pass

    @abstractmethod
    def get_config(self) -> SchedulingConfig:
        """获取当前配置"""
        pass


class IDataService(ABC):
    """数据服务接口"""

    @abstractmethod
    def load_courses(self, file_path: str) -> List[Course]:
        """加载课程数据"""
        pass

    @abstractmethod
    def import_selected_courses(
        self, file_path: str, courses: List[Course]
    ) -> List[SelectedCourse]:
        """导入已选课程"""
        pass

    @abstractmethod
    def export_selected_courses(
        self, selected_courses: List[SelectedCourse], file_path: str
    ) -> bool:
        """导出已选课程"""
        pass

    @abstractmethod
    def export_scheduling_result(self, result: ScheduleResult, file_path: str) -> bool:
        """导出排课结果"""
        pass

    @abstractmethod
    def get_load_report(self) -> Dict[str, Any]:
        """获取数据加载报告"""
        pass


class IUIController(ABC):
    """UI控制器接口"""

    @abstractmethod
    def on_algorithm_config_changed(self, config: SchedulingConfig) -> None:
        """算法配置变化回调"""
        pass

    @abstractmethod
    def on_scheduling_requested(self, courses: List[SelectedCourse]) -> None:
        """排课请求回调"""
        pass

    @abstractmethod
    def on_scheduling_progress(self, progress: float, message: str) -> None:
        """排课进度回调"""
        pass

    @abstractmethod
    def on_scheduling_completed(self, result: ScheduleResult) -> None:
        """排课完成回调"""
        pass

    @abstractmethod
    def on_scheduling_failed(self, error: Exception) -> None:
        """排课失败回调"""
        pass

    @abstractmethod
    def register_event_handler(
        self, event_type: str, handler: Callable[[ServiceEvent], None]
    ) -> None:
        """注册事件处理器"""
        pass


class IEventManager(ABC):
    """事件管理器接口"""

    @abstractmethod
    def emit(self, event: ServiceEvent) -> None:
        """发送事件"""
        pass

    @abstractmethod
    def subscribe(
        self, event_type: str, handler: Callable[[ServiceEvent], None]
    ) -> None:
        """订阅事件"""
        pass

    @abstractmethod
    def unsubscribe(
        self, event_type: str, handler: Callable[[ServiceEvent], None]
    ) -> None:
        """取消订阅"""
        pass
