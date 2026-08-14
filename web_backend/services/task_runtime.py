"""Asynchronous task runtime for web scheduling jobs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
import time
from typing import Dict, List, Optional
from uuid import uuid4

from core.models import SelectedCourse
from core.scheduling.config import SchedulingConfig
from core.scheduling.models import ScheduleResult
from core.services.interfaces import ServiceEvent, SchedulingStatus as ServiceSchedulingStatus

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
    # 🔧 P1 修复：进度百分比，使 HTTP 轮询也能拿到进度（之前 DTO 无此字段）
    percent: int = 0

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
        self.percent = 10

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
        self.percent = 100

    def mark_failed(self, error_message: str) -> None:
        now = datetime.now()
        self.status = TaskStatus.FAILED
        self.message = "排课任务失败"
        self.error_message = error_message
        self.result = None
        self.finished_at = now
        self.updated_at = now
        self.percent = 100

    def mark_cancelled(self) -> None:
        now = datetime.now()
        self.status = TaskStatus.CANCELLED
        self.message = "排课任务已取消，结果不会写入当前会话"
        self.error_message = None
        self.result = None
        self.finished_at = now
        self.updated_at = now
        self.percent = 100


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
            future = self._futures.get(task_id)
            if future is not None and future.cancel():
                # 任务尚在 executor 队列中时不会进入 _run_task，必须在这里
                # 直接收尾；否则它会永久停在 cancel_requested 并阻塞后续提交。
                record.mark_cancelled()
                self._futures.pop(task_id, None)
            return record

    def _run_task(
        self,
        session: WebSessionContext,
        task_id: str,
        selected_courses: List[SelectedCourse],
        config_snapshot: SchedulingConfig,
    ) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            # cancel_task 可能在线程刚启动、Future 已无法 cancel() 时抢先执行。
            # 此时不能再把 CANCEL_REQUESTED 覆盖回 RUNNING。
            if record.cancel_requested:
                record.mark_cancelled()
                self._futures.pop(task_id, None)
                return
            record.mark_running()

        event_manager = getattr(session, "event_manager", None)
        forwarding_handlers = []

        def forward_with_task_id(event_type: str):
            """把核心服务事件补上 task_id 后再交给 WebSocket adapter。"""

            def handler(event: ServiceEvent) -> None:
                if event.data.get("task_id") == task_id:
                    return
                data = dict(event.data)
                data["task_id"] = task_id
                event_manager.emit(
                    ServiceEvent(
                        event_type=event_type,
                        data=data,
                        timestamp=event.timestamp,
                        source="task_runtime",
                    )
                )

            return handler

        if event_manager is not None:
            for event_type in (
                "scheduling_started",
                "scheduling_completed",
                "scheduling_failed",
            ):
                handler = forward_with_task_id(event_type)
                forwarding_handlers.append((event_type, handler))
                event_manager.subscribe(event_type, handler)

        try:
            self._emit_progress(session, record, "正在准备排课数据", 5)

            session.scheduling_service.configure(deepcopy(config_snapshot))
            self._emit_progress(session, record, "正在执行排课求解", 20)

            result = session.scheduling_service.execute(deepcopy(selected_courses))

            if result is None:
                # 保留服务层给出的真实失败原因（例如超时/约束不可满足），
                # 不要统一覆盖成“没有返回有效结果”。取消与失败判定必须原子化，
                # 让先到达的取消请求优先于失败结果。
                service_status = session.scheduling_service.get_status()
                failure_message = (
                    "排课任务执行失败"
                    if service_status == ServiceSchedulingStatus.FAILED
                    else "排课任务没有返回有效结果"
                )
                with self._lock:
                    cancelled = record.cancel_requested
                    if cancelled:
                        record.mark_cancelled()
                    else:
                        record.mark_failed(failure_message)
                if not cancelled:
                    session.set_last_scheduling_result(None)
                return

            self._emit_progress(session, record, "正在汇总排课结果", 90)
            # 用户可能恰好在 execute() 返回后、结果写入前点击取消。
            # 在同一锁内完成“检查取消 + 提交结果”，保证取消先到就不发布结果。
            with self._lock:
                cancelled = record.cancel_requested
                if cancelled:
                    record.mark_cancelled()
                else:
                    record.mark_completed(result)
            if cancelled:
                self._emit_progress(session, record, "排课任务已取消", 100)
                return

            session.set_last_scheduling_result(result)
            self._emit_progress(session, record, "排课任务完成", 100)
        except Exception as exc:  # pragma: no cover
            with self._lock:
                cancelled = record.cancel_requested
                if cancelled:
                    record.mark_cancelled()
                else:
                    record.mark_failed(str(exc))
            if not cancelled:
                session.set_last_scheduling_result(None)
        finally:
            if event_manager is not None:
                for event_type, handler in forwarding_handlers:
                    event_manager.unsubscribe(event_type, handler)
            with self._lock:
                self._futures.pop(task_id, None)

    def _emit_progress(
        self,
        session: WebSessionContext,
        record: SchedulingTaskRecord,
        message: str,
        percent: int,
    ) -> None:
        """发送排课进度事件

        🔧 P1 修复：adapter 一直订阅着 scheduling_progress，但以前没有任何
        地方发出过该事件，导致前端永远收不到进度。同时把 percent 写入
        record，使 HTTP 轮询也能拿到进度。
        """
        with self._lock:
            # 取消请求后的非终态进度不能覆盖“取消中”的消息和百分比。
            if record.cancel_requested and percent < 100:
                return
            record.percent = percent
            record.message = message
            record.updated_at = datetime.now()

        event_manager = getattr(session, "event_manager", None)
        if event_manager is None:
            return

        try:
            event_manager.emit(
                ServiceEvent(
                    event_type="scheduling_progress",
                    data={
                        "message": message,
                        "percent": percent,
                        "task_id": record.task_id,
                    },
                    timestamp=time.time(),
                    source="task_runtime",
                )
            )
        except Exception as exc:  # pragma: no cover - 进度推送不得影响排课
            print(f"⚠️ 进度事件发送失败: {exc}")


_task_runtime: Optional[SchedulingTaskRuntime] = None


def get_task_runtime() -> SchedulingTaskRuntime:
    global _task_runtime
    if _task_runtime is None:
        _task_runtime = SchedulingTaskRuntime()
    return _task_runtime
