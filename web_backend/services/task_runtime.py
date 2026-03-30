"""Asynchronous task runtime for web scheduling jobs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from core.models import SelectedCourse
from core.scheduling.config import SchedulingConfig
from core.scheduling.models import ScheduleResult

from ..state import WebSessionContext


class TaskAlreadyRunningError(RuntimeError):
    """Raised when a new task is submitted while another one is active."""


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SchedulingTaskRecord:
    """In-memory record for a single scheduling task."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = "排课任务已提交，等待后台执行"
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    selected_course_ids: List[str] = field(default_factory=list)
    result: Optional[ScheduleResult] = None
    cancel_requested: bool = False

    @property
    def is_finished(self) -> bool:
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }

    @property
    def is_active(self) -> bool:
        return self.status in {
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.CANCEL_REQUESTED,
        }

    @property
    def can_cancel(self) -> bool:
        return self.status in {TaskStatus.PENDING, TaskStatus.RUNNING}

    @property
    def has_result(self) -> bool:
        return self.status == TaskStatus.COMPLETED and self.result is not None

    def mark_running(self) -> None:
        now = datetime.now()
        self.status = TaskStatus.RUNNING
        self.message = "排课任务正在后台执行"
        self.started_at = now
        self.updated_at = now

    def request_cancel(self) -> None:
        now = datetime.now()
        self.cancel_requested = True
        if not self.is_finished:
            self.status = TaskStatus.CANCEL_REQUESTED
            self.message = "取消请求已提交，等待后台结束当前求解"
            self.updated_at = now

    def mark_completed(self, result: ScheduleResult) -> None:
        now = datetime.now()
        self.status = TaskStatus.COMPLETED
        self.message = "排课任务完成"
        self.result = result
        self.error_message = None
        self.finished_at = now
        self.updated_at = now

    def mark_failed(self, error_message: str) -> None:
        now = datetime.now()
        self.status = TaskStatus.FAILED
        self.message = "排课任务失败"
        self.error_message = error_message
        self.result = None
        self.finished_at = now
        self.updated_at = now

    def mark_cancelled(self) -> None:
        now = datetime.now()
        self.status = TaskStatus.CANCELLED
        self.message = "排课任务已取消，结果不会写入当前会话"
        self.error_message = None
        self.result = None
        self.finished_at = now
        self.updated_at = now


class SchedulingTaskRuntime:
    """Thread-safe single-task runtime for scheduling jobs."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="web-scheduling")
        self._tasks: Dict[str, SchedulingTaskRecord] = {}
        self._futures: Dict[str, Future] = {}

    def _get_active_task_locked(self) -> Optional[SchedulingTaskRecord]:
        for record in reversed(list(self._tasks.values())):
            if record.is_active:
                return record
        return None

    def get_task(self, task_id: str) -> Optional[SchedulingTaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_active_task(self) -> Optional[SchedulingTaskRecord]:
        with self._lock:
            return self._get_active_task_locked()

    def submit_task(
        self,
        session: WebSessionContext,
        selected_course_ids: Optional[List[str]] = None,
    ) -> SchedulingTaskRecord:
        selected_courses = session.snapshot_selected_courses(selected_course_ids)
        config_snapshot = session.snapshot_scheduling_config()

        with self._lock:
            active_task = self._get_active_task_locked()
            if active_task is not None:
                raise TaskAlreadyRunningError(f"当前已有任务正在运行：{active_task.task_id}")

            task_id = str(uuid4())
            record = SchedulingTaskRecord(
                task_id=task_id,
                message="排课任务已提交，等待后台执行",
                selected_course_ids=[course_id for course_id in (selected_course_ids or [])],
            )
            self._tasks[task_id] = record
            session.register_task_record(record)
            session.invalidate_scheduling_result()

            if not selected_courses:
                record.mark_failed("没有可排课的课程")
                return record

            future = self._executor.submit(
                self._run_task,
                session,
                task_id,
                selected_courses,
                config_snapshot,
            )
            self._futures[task_id] = future
            return record

    def cancel_task(self, task_id: str) -> Optional[SchedulingTaskRecord]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            if record.is_finished:
                return record

            record.request_cancel()
            return record

    def _run_task(
        self,
        session: WebSessionContext,
        task_id: str,
        selected_courses: List[SelectedCourse],
        config_snapshot: SchedulingConfig,
    ) -> None:
        record = self.get_task(task_id)
        if record is None:
            return

        try:
            record.mark_running()
            session.scheduling_service.configure(deepcopy(config_snapshot))

            result = session.scheduling_service.execute(deepcopy(selected_courses))

            if record.cancel_requested:
                record.mark_cancelled()
                return

            if result is None:
                record.mark_failed("排课任务没有返回有效结果")
                session.set_last_scheduling_result(None)
                return

            record.mark_completed(result)
            session.set_last_scheduling_result(result)
        except Exception as exc:  # pragma: no cover
            if record.cancel_requested:
                record.mark_cancelled()
            else:
                record.mark_failed(str(exc))
                session.set_last_scheduling_result(None)
        finally:
            with self._lock:
                self._futures.pop(task_id, None)


_task_runtime: Optional[SchedulingTaskRuntime] = None


def get_task_runtime() -> SchedulingTaskRuntime:
    global _task_runtime
    if _task_runtime is None:
        _task_runtime = SchedulingTaskRuntime()
    return _task_runtime
