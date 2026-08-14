"""Async scheduling runtime concurrency and cancellation regression checks."""

from concurrent.futures import Future
from threading import Event

import pytest

from core.scheduling.config import SchedulingConfig
from core.scheduling.models import ScheduleResult, ScheduleStatus
from web_backend.services.task_runtime import (
    SchedulingTaskRuntime,
    TaskAlreadyRunningError,
    TaskStatus,
)


class _BlockingSchedulingService:
    def __init__(self, started: Event, release: Event, result=None) -> None:
        self.started = started
        self.release = release
        self.result = result

    def configure(self, _config) -> None:
        pass

    def execute(self, _courses):
        self.started.set()
        assert self.release.wait(5), "test did not release the scheduling worker"
        return self.result

    def get_status(self):  # pragma: no cover - only used when result is None
        raise AssertionError("unexpected get_status call")


class _SessionStub:
    def __init__(self, course, service) -> None:
        self._course = course
        self.scheduling_service = service
        self.scheduling_config = SchedulingConfig()
        self.event_manager = None
        self.current_task = None
        self.last_scheduling_result = None

    def snapshot_selected_courses(self, _course_ids=None):
        return [self._course]

    def snapshot_scheduling_config(self):
        return self.scheduling_config

    def register_task_record(self, record) -> None:
        self.current_task = record

    def invalidate_scheduling_result(self) -> None:
        self.last_scheduling_result = None

    def set_last_scheduling_result(self, result) -> None:
        self.last_scheduling_result = result


def _wait(future: Future) -> None:
    future.result(timeout=5)


def test_runtime_rejects_concurrent_submission_and_cancelled_result_is_not_published(
    make_course,
):
    started = Event()
    release = Event()
    result = ScheduleResult(
        schedule_id="late-result",
        selected_courses=[make_course("C1")],
        status=ScheduleStatus.SUCCESS,
    )
    session = _SessionStub(
        make_course("C1"),
        _BlockingSchedulingService(started, release, result),
    )
    runtime = SchedulingTaskRuntime()

    record = runtime.submit_task(session)
    assert started.wait(5)
    with pytest.raises(TaskAlreadyRunningError):
        runtime.submit_task(session)

    cancelled = runtime.cancel_task(record.task_id)
    assert cancelled is record
    assert cancelled.status is TaskStatus.CANCEL_REQUESTED

    release.set()
    _wait(runtime._futures[record.task_id])

    assert record.status is TaskStatus.CANCELLED
    assert record.result is None
    assert session.last_scheduling_result is None
    assert runtime.get_active_task() is None
    runtime._executor.shutdown(wait=True)


def test_runtime_immediately_finishes_a_task_cancelled_before_worker_start(make_course):
    session = _SessionStub(make_course("C1"), object())
    runtime = SchedulingTaskRuntime()
    blocker = Event()
    runtime._executor.submit(blocker.wait)

    record = runtime.submit_task(session)
    cancelled = runtime.cancel_task(record.task_id)

    assert cancelled is record
    assert record.status is TaskStatus.CANCELLED
    assert record.is_finished is True
    assert record.task_id not in runtime._futures
    assert runtime.get_active_task() is None

    blocker.set()
    runtime._executor.shutdown(wait=True)
