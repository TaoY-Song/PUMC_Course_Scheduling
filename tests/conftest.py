"""Shared fixtures for the PUMC scheduling test suite."""

import sys
from pathlib import Path

import pytest

# Make the project root importable when pytest is invoked from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.credit_manager import CreditManager  # noqa: E402
from core.models import Course, SelectedCourse, TimeSlot  # noqa: E402

#: Category used across the tests; matches a real category in CreditManager.
ELECTIVE = "选修课 - 学位选修"


@pytest.fixture
def make_course():
    """Build a SelectedCourse with one weekly time slot.

    Keeping this a factory (rather than a constant) avoids tests sharing
    mutable course objects, which previously masked state-leak bugs.
    """

    def _make(
        code: str,
        weekday: int = 1,
        start_section: int = 3,
        *,
        campus: str = "东单",
        credits: float = 1.0,
        category: str = ELECTIVE,
        weeks=None,
        online: bool = False,
        end_section: int | None = None,
    ) -> SelectedCourse:
        course = Course(
            code,
            code,
            "d",
            "学位选修",
            1,
            campus,
            "t",
            credits,
            16,
        )
        slots = []
        if not online:
            slots = [
                TimeSlot(
                    weekday,
                    start_section,
                    end_section if end_section is not None else start_section + 1,
                    weeks if weeks is not None else list(range(1, 17)),
                )
            ]
        return SelectedCourse(course, 1, slots, online, category)

    return _make


@pytest.fixture
def credit_manager():
    """A CreditManager with every requirement zeroed except the elective one.

    Zeroing the other categories keeps the tests focused: otherwise every
    schedule is judged against six unrelated requirements.
    """

    def _build(required: float = 4.0, completed: float = 0.0) -> CreditManager:
        cm = CreditManager()
        for category in list(cm.requirements):
            cm.set_required_credits(category, 0.0)
        cm.set_required_credits(ELECTIVE, required)
        if completed:
            cm.set_completed_credits(ELECTIVE, completed)
        return cm

    return _build


class RecordingEventManager:
    """Minimal IEventManager stand-in that records emitted events."""

    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)

    def subscribe(self, event_type, handler) -> None:  # pragma: no cover
        pass

    @property
    def event_types(self):
        return [event.event_type for event in self.events]

    def first(self, event_type):
        return next((e for e in self.events if e.event_type == event_type), None)


@pytest.fixture
def event_recorder():
    return RecordingEventManager()
