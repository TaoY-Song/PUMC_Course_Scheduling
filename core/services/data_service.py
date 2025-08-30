"""
数据服务实现 - 封装数据加载和导出的服务层

这个模块实现了IDataService接口，提供统一的数据操作服务。
"""

import time
from typing import List, Dict, Any

from .interfaces import IDataService, ServiceEvent
from ..models import Course, SelectedCourse
from ..data_loader import CourseDataLoader
from ..import_export import SelectedCourseImporter, SelectedCourseExporter
from ..scheduling.models import ScheduleResult


class DataService(IDataService):
    """数据服务实现类"""

    def __init__(self, event_manager=None):
        """初始化数据服务"""
        self._course_loader = CourseDataLoader()
        self._importer = SelectedCourseImporter()
        self._exporter = SelectedCourseExporter()
        self._event_manager = event_manager

    def load_courses(self, file_path: str) -> List[Course]:
        """加载课程数据"""
        try:
            # 发送开始加载事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_loading_started",
                    data={"file_path": file_path, "operation": "load_courses"},
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            # 执行加载
            success = self._course_loader.load_from_excel(file_path)

            if success:
                courses = self._course_loader.get_courses()

                # 发送加载完成事件
                if self._event_manager:
                    event = ServiceEvent(
                        event_type="data_loading_completed",
                        data={
                            "file_path": file_path,
                            "operation": "load_courses",
                            "course_count": len(courses),
                            "report": self._course_loader.get_load_report(),
                        },
                        timestamp=time.time(),
                        source="data_service",
                    )
                    self._event_manager.emit(event)

                return courses
            else:
                raise RuntimeError("课程数据加载失败")

        except Exception as e:
            # 发送加载失败事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_loading_failed",
                    data={
                        "file_path": file_path,
                        "operation": "load_courses",
                        "error": str(e),
                    },
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            raise e

    def import_selected_courses(
        self, file_path: str, courses: List[Course]
    ) -> List[SelectedCourse]:
        """导入已选课程"""
        try:
            # 发送开始导入事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_loading_started",
                    data={
                        "file_path": file_path,
                        "operation": "import_selected_courses",
                    },
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            # 创建临时的CourseDataLoader来提供课程查找功能
            temp_loader = CourseDataLoader()
            temp_loader.courses = courses  # 直接设置课程列表

            # 执行导入
            selected_courses, import_report = self._importer.import_from_excel(
                file_path, temp_loader
            )

            # 发送导入完成事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_loading_completed",
                    data={
                        "file_path": file_path,
                        "operation": "import_selected_courses",
                        "selected_count": len(selected_courses),
                        "report": import_report,
                    },
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            return selected_courses

        except Exception as e:
            # 发送导入失败事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_loading_failed",
                    data={
                        "file_path": file_path,
                        "operation": "import_selected_courses",
                        "error": str(e),
                    },
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            raise e

    def export_selected_courses(
        self, selected_courses: List[SelectedCourse], file_path: str
    ) -> bool:
        """导出已选课程"""
        try:
            # 发送开始导出事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_export_started",
                    data={
                        "file_path": file_path,
                        "operation": "export_selected_courses",
                    },
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            # 执行导出
            success = self._exporter.export_to_excel(selected_courses, file_path)

            if success:
                # 发送导出完成事件
                if self._event_manager:
                    event = ServiceEvent(
                        event_type="data_export_completed",
                        data={
                            "file_path": file_path,
                            "operation": "export_selected_courses",
                            "course_count": len(selected_courses),
                        },
                        timestamp=time.time(),
                        source="data_service",
                    )
                    self._event_manager.emit(event)

            return success

        except Exception as e:
            # 发送导出失败事件
            if self._event_manager:
                event = ServiceEvent(
                    event_type="data_export_failed",
                    data={
                        "file_path": file_path,
                        "operation": "export_selected_courses",
                        "error": str(e),
                    },
                    timestamp=time.time(),
                    source="data_service",
                )
                self._event_manager.emit(event)

            raise e

    def export_scheduling_result(self, result: ScheduleResult, file_path: str) -> bool:
        """导出排课结果"""
        try:
            # 将排课结果转换为已选课程列表进行导出
            return self.export_selected_courses(result.selected_courses, file_path)

        except Exception as e:
            raise e

    def get_load_report(self) -> Dict[str, Any]:
        """获取数据加载报告"""
        return self._course_loader.get_load_report()
