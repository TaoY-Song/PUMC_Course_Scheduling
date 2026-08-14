"""P1: WebSocket events must survive the worker-thread boundary."""

import asyncio
import threading
import time

import pytest

from core.services.event_manager import EventManager
from core.services.interfaces import ServiceEvent
from web_backend.services.event_adapter import WebSocketEventAdapter


def _emit_from_worker(event_manager, event_type, data):
    """Emit exactly the way the scheduling task does: off the event loop."""

    def worker():
        event_manager.emit(
            ServiceEvent(
                event_type=event_type,
                data=data,
                timestamp=time.time(),
                source="test-worker",
            )
        )

    thread = threading.Thread(target=worker, name="fake-scheduling-worker")
    thread.start()
    thread.join()


@pytest.mark.parametrize(
    "core_event,ws_event,payload,expected_key,expected_value",
    [
        (
            "scheduling_progress",
            "scheduling.progress",
            {"task_id": "task-1", "message": "正在执行排课求解", "percent": 20},
            "percent",
            20,
        ),
        (
            "scheduling_failed",
            "scheduling.failed",
            {"task_id": "task-1", "error": "无可行解"},
            "error",
            "无可行解",
        ),
        # The core layer emits data_loading_completed; the adapter used to
        # subscribe to a "courses_loaded" event that nothing ever emitted.
        (
            "data_loading_completed",
            "courses.loaded",
            {"count": 42},
            "count",
            42,
        ),
    ],
)
def test_events_cross_the_thread_boundary(
    core_event, ws_event, payload, expected_key, expected_value
):
    async def scenario():
        manager = EventManager()
        adapter = WebSocketEventAdapter(manager)
        adapter.bind_loop(asyncio.get_running_loop())

        received = []

        async def handler(data):
            received.append(data)

        adapter.register_handler(ws_event, handler)
        _emit_from_worker(manager, core_event, payload)
        await asyncio.sleep(0.3)  # let run_coroutine_threadsafe drain
        return received

    received = asyncio.run(scenario())

    assert len(received) == 1, "event never reached the WebSocket handler"
    assert received[0][expected_key] == expected_value
    if core_event.startswith("scheduling_"):
        assert received[0]["task_id"] == "task-1"


def test_all_scheduling_events_keep_task_id():
    """Regression: clients need task_id to reject stale task messages."""
    async def scenario():
        manager = EventManager()
        adapter = WebSocketEventAdapter(manager)
        adapter.bind_loop(asyncio.get_running_loop())
        received = {}

        for ws_event in (
            "scheduling.started",
            "scheduling.progress",
            "scheduling.completed",
            "scheduling.failed",
        ):
            async def handler(data, event=ws_event):
                received[event] = data
            adapter.register_handler(ws_event, handler)

        for core_event in (
            "scheduling_started",
            "scheduling_progress",
            "scheduling_completed",
            "scheduling_failed",
        ):
            manager.emit(
                ServiceEvent(
                    event_type=core_event,
                    data={"task_id": "task-current"},
                    timestamp=time.time(),
                    source="test",
                )
            )
        await asyncio.sleep(0.2)
        return received

    received = asyncio.run(scenario())
    assert set(received) == {
        "scheduling.started",
        "scheduling.progress",
        "scheduling.completed",
        "scheduling.failed",
    }
    assert all(payload["task_id"] == "task-current" for payload in received.values())


def test_same_thread_emit_still_works():
    """Binding a loop must not break the in-loop path."""

    async def scenario():
        manager = EventManager()
        adapter = WebSocketEventAdapter(manager)
        adapter.bind_loop(asyncio.get_running_loop())

        received = []

        async def handler(data):
            received.append(data)

        adapter.register_handler("scheduling.progress", handler)
        manager.emit(
            ServiceEvent(
                event_type="scheduling_progress",
                data={"task_id": "task-loop", "message": "同线程", "percent": 55},
                timestamp=time.time(),
                source="test-loop",
            )
        )
        await asyncio.sleep(0.2)
        return received

    assert len(asyncio.run(scenario())) == 1


def test_event_handler_can_reemit_same_event_type_without_deadlock():
    """Task runtime enriches a core event by re-emitting it with task_id."""
    manager = EventManager()
    received = []

    def handler(event):
        received.append(event.data.copy())
        if "task_id" not in event.data:
            manager.emit(
                ServiceEvent(
                    event_type=event.event_type,
                    data={**event.data, "task_id": "task-1"},
                    timestamp=event.timestamp,
                    source="enricher",
                )
            )

    manager.subscribe("scheduling_started", handler)
    manager.emit(
        ServiceEvent(
            event_type="scheduling_started",
            data={"course_count": 1},
            timestamp=time.time(),
            source="service",
        )
    )

    assert [item.get("task_id") for item in received] == [None, "task-1"]


def test_unbound_adapter_degrades_without_crashing():
    """No loop bound yet: warn and drop, never raise into the solver thread."""
    manager = EventManager()
    adapter = WebSocketEventAdapter(manager)  # bind_loop deliberately not called
    received = []

    async def handler(data):
        received.append(data)

    adapter.register_handler("scheduling.progress", handler)
    _emit_from_worker(manager, "scheduling_progress", {"message": "x", "percent": 1})

    assert received == []


def test_task_record_tracks_progress_percent():
    """P1: the DTO had no percent field, so HTTP polling could not show progress."""
    from web_backend.services.task_runtime import SchedulingTaskRecord

    record = SchedulingTaskRecord(task_id="t1")
    assert record.percent == 0

    record.mark_running()
    assert 0 < record.percent < 100

    record.mark_completed(result=None)
    assert record.percent == 100


def test_task_status_payload_includes_percent():
    from web_backend.api.scheduling import _task_base_payload
    from web_backend.services.task_runtime import SchedulingTaskRecord

    record = SchedulingTaskRecord(task_id="t1")
    record.mark_running()

    payload = _task_base_payload(record)

    assert "percent" in payload
    assert payload["percent"] == record.percent
