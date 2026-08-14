"""P2: time-slot occupancy keys must use one consistent ordering."""

from core.models import SelectedCourse
from core.scheduling.config import SchedulingConfig
from core.scheduling.engine import SchedulingEngine


def _bare_engine(credit_manager):
    engine = object.__new__(SchedulingEngine)
    engine.config = SchedulingConfig()
    engine.credit_manager = credit_manager()
    engine._timed_out = False
    return engine


def test_written_keys_are_detected_as_conflicts(credit_manager, make_course):
    """The original bug: writer and reader used different tuple orders.

    _simple_schedule_timed_courses wrote (week, weekday, section) while
    _has_time_conflict read (weekday, section, week), so occupancy recorded by
    the simple path was invisible to the conflict check.
    """
    engine = _bare_engine(credit_manager)
    course = make_course("A", weekday=2, start_section=3, weeks=[1, 2, 3])

    used = set()
    engine._add_course_time_slots(course, used)

    assert used, "no occupancy keys were recorded"
    assert engine._has_time_conflict(course, used) is True


def test_allocate_time_slot_respects_recorded_occupancy(credit_manager, make_course):
    """_allocate_time_slot read the other key order, so it never saw conflicts."""
    engine = _bare_engine(credit_manager)

    used = set()
    # Occupy every section the allocator prefers, for the weeks it would pick.
    for weekday in range(1, 6):
        for start in (3, 7, 1, 9):
            for section in (start, start + 1):
                for week in range(1, 9):
                    used.add((weekday, section, week))

    slot = engine._allocate_time_slot(1, used)

    assert slot is None, "allocator handed out an already-occupied slot"


def test_free_slot_is_still_allocatable(credit_manager):
    engine = _bare_engine(credit_manager)

    slot = engine._allocate_time_slot(1, set())

    assert slot is not None
    assert 1 <= slot.weekday <= 5


def test_distinct_courses_do_not_false_positive(credit_manager, make_course):
    """Different weekdays must not be reported as conflicting."""
    engine = _bare_engine(credit_manager)
    monday = make_course("A", weekday=1, start_section=3)
    wednesday = make_course("B", weekday=3, start_section=3)

    used = set()
    engine._add_course_time_slots(monday, used)

    assert engine._has_time_conflict(wednesday, used) is False


def test_non_overlapping_weeks_do_not_conflict(credit_manager, make_course):
    engine = _bare_engine(credit_manager)
    early = make_course("A", weekday=1, start_section=3, weeks=[1, 2])
    late = make_course("B", weekday=1, start_section=3, weeks=[9, 10])

    used = set()
    engine._add_course_time_slots(early, used)

    assert engine._has_time_conflict(late, used) is False


def test_key_ordering_is_weekday_section_week(credit_manager, make_course):
    """Pin the documented convention so a future edit cannot silently flip it."""
    engine = _bare_engine(credit_manager)
    course = make_course("A", weekday=4, start_section=5, end_section=5, weeks=[7])

    keys = list(engine._time_slot_keys(course))

    assert keys == [(4, 5, 7)]


def test_model_level_conflict_helper_agrees(make_course):
    """core.models.SelectedCourse.has_time_conflict is the shared helper."""
    a = make_course("A", weekday=1, start_section=3)
    b = make_course("B", weekday=1, start_section=3)
    c = make_course("C", weekday=2, start_section=3)

    assert SelectedCourse.has_time_conflict(a, b) is True
    assert SelectedCourse.has_time_conflict(a, c) is False
