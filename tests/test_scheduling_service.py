"""P0-1: a failed or timed-out engine result must never be reported as success."""

import pytest

from core.scheduling.models import ScheduleResult, ScheduleStatus
from core.services.interfaces import SchedulingStatus
from core.services.scheduling_service import SchedulingService


class _StubEngine:
    """Engine stub returning a canned result, mimicking the real contract."""

    def __init__(self, status, *, courses=(), warning=None):
        self._status = status
        self._courses = list(courses)
        self._warning = warning
        self.received_max_solutions = None

    def generate_schedules(self, courses, max_solutions=None):
        self.received_max_solutions = max_solutions
        result = ScheduleResult(
            schedule_id="stub",
            status=self._status,
            selected_courses=self._courses,
            solve_time_seconds=0.1,
            total_courses_considered=len(courses),
        )
        if self._warning:
            result.add_warning(self._warning)
        return [result]


def _service(engine, credit_manager, event_recorder):
    service = SchedulingService(
        event_manager=event_recorder, credit_manager=credit_manager()
    )
    service._engine = engine
    return service


def test_failed_result_is_not_reported_as_completed(
    credit_manager, event_recorder, make_course
):
    """The original bug: engine returned FAILED but the service said COMPLETED."""
    engine = _StubEngine(ScheduleStatus.FAILED, warning="排课算法执行失败：内部异常")
    service = _service(engine, credit_manager, event_recorder)

    result = service.execute([make_course("A")])

    assert result is None
    assert service.get_status() is SchedulingStatus.FAILED
    assert "scheduling_completed" not in event_recorder.event_types
    assert "scheduling_failed" in event_recorder.event_types


def test_failure_reason_reaches_the_event_payload(
    credit_manager, event_recorder, make_course
):
    engine = _StubEngine(ScheduleStatus.FAILED, warning="排课算法执行失败：内部异常")
    service = _service(engine, credit_manager, event_recorder)

    service.execute([make_course("A")])

    failed = event_recorder.first("scheduling_failed")
    assert failed is not None
    assert "内部异常" in failed.data["error"]


def test_timeout_without_solution_is_a_failure(
    credit_manager, event_recorder, make_course
):
    engine = _StubEngine(
        ScheduleStatus.TIMEOUT, warning="求解已达时间上限（2 秒）且未找到可行方案"
    )
    service = _service(engine, credit_manager, event_recorder)

    result = service.execute([make_course("A")])

    assert result is None
    assert service.get_status() is SchedulingStatus.FAILED
    assert "scheduling_completed" not in event_recorder.event_types
    failed = event_recorder.first("scheduling_failed")
    assert failed.data.get("timeout") is True


def test_partial_result_with_courses_is_a_success(
    credit_manager, event_recorder, make_course
):
    """PARTIAL means soft constraints were missed, not that scheduling failed."""
    courses = [make_course("A"), make_course("B", weekday=2)]
    engine = _StubEngine(ScheduleStatus.PARTIAL, courses=courses)
    service = _service(engine, credit_manager, event_recorder)

    result = service.execute(courses)

    assert result is not None
    assert service.get_status() is SchedulingStatus.COMPLETED
    assert "scheduling_completed" in event_recorder.event_types


def test_success_result_is_reported_as_completed(
    credit_manager, event_recorder, make_course
):
    courses = [make_course("A")]
    engine = _StubEngine(ScheduleStatus.SUCCESS, courses=courses)
    service = _service(engine, credit_manager, event_recorder)

    result = service.execute(courses)

    assert result is not None
    assert service.get_status() is SchedulingStatus.COMPLETED


def test_engine_exception_is_reported_as_failure(
    credit_manager, event_recorder, make_course
):
    class _Boom:
        def generate_schedules(self, courses, max_solutions=None):
            raise RuntimeError("solver exploded")

    service = _service(_Boom(), credit_manager, event_recorder)

    result = service.execute([make_course("A")])

    assert result is None
    assert service.get_status() is SchedulingStatus.FAILED
    assert "scheduling_completed" not in event_recorder.event_types


def test_service_passes_configured_max_solutions_to_engine(
    credit_manager, event_recorder, make_course
):
    """P0-4: max_solutions used to be hardcoded to 1, ignoring the UI setting."""
    from core.scheduling.config import SchedulingConfig

    courses = [make_course("A")]
    engine = _StubEngine(ScheduleStatus.SUCCESS, courses=courses)
    service = _service(engine, credit_manager, event_recorder)
    service.configure(SchedulingConfig(max_solutions=7))
    service._engine = engine  # configure() rebuilds the engine

    service.execute(courses)

    assert engine.received_max_solutions == 7
