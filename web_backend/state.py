"""Single-session state container for the web application."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from core.credit_manager import CreditManager
from core.models import Course, SelectedCourse, TimeSlot
from core.scheduling.config import SchedulingConfig
from core.scheduling.models import ScheduleResult
from core.services import get_service_factory
from core.services.interfaces import IDataService, IEventManager, ISchedulingService


def _default_artifacts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "exports"


@dataclass
class WebSessionContext:
    service_factory: object = field(default_factory=get_service_factory)
    credit_manager: CreditManager = field(default_factory=CreditManager)
    scheduling_config: SchedulingConfig = field(default_factory=SchedulingConfig)
    loaded_courses: List[Course] = field(default_factory=list)
    loaded_course_file: Optional[str] = None
    selected_courses: Dict[str, SelectedCourse] = field(default_factory=dict)
    course_index: Dict[str, List[Course]] = field(default_factory=dict)
    last_scheduling_result: Optional[ScheduleResult] = None
    current_task: Optional[Any] = None
    current_task_id: Optional[str] = None
    task_records: Dict[str, Any] = field(default_factory=dict)
    artifacts_dir: Path = field(default_factory=_default_artifacts_dir)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    data_service: IDataService = field(init=False, repr=False)
    scheduling_service: ISchedulingService = field(init=False, repr=False)
    event_manager: IEventManager = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.data_service = self.service_factory.get_data_service()
        self.scheduling_service = self.service_factory.get_scheduling_service(self.credit_manager)
        self.event_manager = self.service_factory.get_event_manager()
        self.scheduling_config = self.scheduling_service.get_config()

    def rebuild_course_index(self) -> None:
        index: Dict[str, List[Course]] = {}
        for course in self.loaded_courses:
            index.setdefault(course.code.upper(), []).append(course)
        self.course_index = index

    def invalidate_scheduling_result(self) -> None:
        self.last_scheduling_result = None

    def set_loaded_courses(
        self,
        courses: List[Course],
        file_path: Optional[str] = None,
        reset_selection: bool = True,
    ) -> None:
        with self._lock:
            self.loaded_courses = list(courses)
            self.loaded_course_file = file_path
            self.rebuild_course_index()
            if reset_selection:
                self.selected_courses.clear()
                self.invalidate_scheduling_result()

    def find_courses(self, course_code: str, class_index: Optional[int] = None) -> List[Course]:
        matches = self.course_index.get(course_code.strip().upper(), [])
        if class_index is None:
            return list(matches)
        return [course for course in matches if course.class_num == class_index]

    def get_selected_course(self, course_id: str) -> Optional[SelectedCourse]:
        return self.selected_courses.get(course_id)

    def list_selected_courses(self) -> List[SelectedCourse]:
        return list(self.selected_courses.values())

    def snapshot_selected_courses(
        self,
        course_ids: Optional[List[str]] = None,
    ) -> List[SelectedCourse]:
        with self._lock:
            if course_ids:
                selected = [
                    self.selected_courses[course_id]
                    for course_id in course_ids
                    if course_id in self.selected_courses
                ]
            else:
                selected = list(self.selected_courses.values())
            return deepcopy(selected)

    def snapshot_scheduling_config(self) -> SchedulingConfig:
        with self._lock:
            return deepcopy(self.scheduling_config)

    def add_selected_course(
        self,
        course: Course,
        class_index: int,
        *,
        is_online: Optional[bool] = None,
        custom_category: Optional[str] = None,
        is_category_locked: bool = False,
        time_slots: Optional[List[TimeSlot]] = None,
    ) -> Tuple[str, SelectedCourse]:
        selected = SelectedCourse(
            course=course,
            class_num=class_index,
            time_slots=list(time_slots or []),
            is_online=course.is_online if is_online is None else is_online,
            custom_category=custom_category or "",
        )
        selected.is_category_locked = is_category_locked

        selected_id = str(uuid4())
        self.selected_courses[selected_id] = selected
        self.invalidate_scheduling_result()
        return selected_id, selected

    def replace_selected_courses(self, courses: List[SelectedCourse]) -> None:
        with self._lock:
            self.selected_courses = {}
            for course in courses:
                if not hasattr(course, "is_category_locked"):
                    course.is_category_locked = False
                self.selected_courses[str(uuid4())] = course
            self.invalidate_scheduling_result()

    def remove_selected_course(self, course_id: str) -> bool:
        removed = self.selected_courses.pop(course_id, None) is not None
        if removed:
            self.invalidate_scheduling_result()
        return removed

    def clear_selected_courses(self) -> None:
        self.selected_courses.clear()
        self.invalidate_scheduling_result()

    def add_time_slot(self, course_id: str, time_slot: TimeSlot) -> Optional[SelectedCourse]:
        selected = self.selected_courses.get(course_id)
        if not selected:
            return None
        selected.time_slots.append(time_slot)
        self.invalidate_scheduling_result()
        return selected

    def update_time_slot(
        self,
        course_id: str,
        time_slot_index: int,
        time_slot: TimeSlot,
    ) -> Optional[SelectedCourse]:
        selected = self.selected_courses.get(course_id)
        if not selected or time_slot_index < 0 or time_slot_index >= len(selected.time_slots):
            return None
        selected.time_slots[time_slot_index] = time_slot
        self.invalidate_scheduling_result()
        return selected

    def delete_time_slot(self, course_id: str, time_slot_index: int) -> Optional[SelectedCourse]:
        selected = self.selected_courses.get(course_id)
        if not selected or time_slot_index < 0 or time_slot_index >= len(selected.time_slots):
            return None
        del selected.time_slots[time_slot_index]
        self.invalidate_scheduling_result()
        return selected

    def set_last_scheduling_result(self, result: Optional[ScheduleResult]) -> None:
        self.last_scheduling_result = result

    def clone_credit_manager_for_status(self) -> CreditManager:
        snapshot = deepcopy(self.credit_manager)
        for requirement in snapshot.requirements.values():
            requirement.completed_credits = requirement.base_completed_credits

        for selected_course in self.selected_courses.values():
            category = selected_course.custom_category or selected_course.course.category
            snapshot.add_completed_credits(category, selected_course.course.credits)

        return snapshot

    def register_task_record(self, task_record: Any) -> None:
        with self._lock:
            self.task_records[task_record.task_id] = task_record
            self.current_task = task_record
            self.current_task_id = task_record.task_id

    def get_task_record(self, task_id: str) -> Optional[Any]:
        with self._lock:
            return self.task_records.get(task_id)

    def update_task_record(self, task_id: str, **changes: Any) -> Optional[Any]:
        with self._lock:
            task_record = self.task_records.get(task_id)
            if task_record is None:
                return None

            for key, value in changes.items():
                setattr(task_record, key, value)

            if self.current_task_id == task_id:
                self.current_task = task_record

            return task_record

    def clear_active_task_record(self, task_id: Optional[str] = None) -> None:
        with self._lock:
            if task_id is None or self.current_task_id == task_id:
                self.current_task = None
                self.current_task_id = None


_web_session_context: Optional[WebSessionContext] = None


def get_web_session_context() -> WebSessionContext:
    global _web_session_context
    if _web_session_context is None:
        _web_session_context = WebSessionContext()
    return _web_session_context
