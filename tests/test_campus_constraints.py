"""P0-4d: the campus transition time setting must actually gate cross-campus days."""

import pytest

from core.scheduling.config import CampusConflictMode, SchedulingConfig
from core.scheduling.constraints import ConstraintChecker
from core.scheduling.engine import SchedulingEngine


def _conflicts(courses, credit_manager, *, mode, min_transfer):
    config = SchedulingConfig(
        campus_conflict_mode=mode, min_campus_transfer_time=min_transfer
    )
    return ConstraintChecker(config, credit_manager()).check_campus_conflicts(courses)


@pytest.mark.parametrize(
    "min_transfer,expected_conflicts",
    [
        (0, 0),
        (2, 0),
        (4, 0),   # actual gap is exactly 4 sections
        (5, 1),   # needs more than available
        (8, 1),
    ],
)
def test_period_mode_honours_min_transfer_time(
    credit_manager, make_course, min_transfer, expected_conflicts
):
    """The original bug: PERIOD mode used hardcoded 1-4/5-8/9-10 windows.

    Sections 1-2 then 7-8 leaves a 4-section gap, so the verdict must depend on
    the configured requirement rather than a fixed period table.
    """
    east = make_course("A", weekday=1, start_section=1, campus="东单")
    west = make_course("B", weekday=1, start_section=7, campus="清华")

    conflicts = _conflicts(
        [east, west], credit_manager, mode=CampusConflictMode.PERIOD, min_transfer=min_transfer
    )

    assert len(conflicts) == expected_conflicts


def test_engine_period_mode_rejects_insufficient_transfer_gap(credit_manager, make_course):
    """Regression: the live search must enforce the same transfer rule as validation."""
    config = SchedulingConfig(
        campus_conflict_mode=CampusConflictMode.PERIOD,
        min_campus_transfer_time=5,
    )
    engine = SchedulingEngine(config, credit_manager(required=2.0))
    east = make_course("A", weekday=1, start_section=1, campus="东单")
    west = make_course("B", weekday=1, start_section=7, campus="清华")

    assert engine._is_campus_compatible(west, [east]) is False


def test_same_campus_never_conflicts(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, campus="东单")
    b = make_course("B", weekday=1, start_section=3, campus="东单")

    conflicts = _conflicts(
        [a, b], credit_manager, mode=CampusConflictMode.PERIOD, min_transfer=8
    )

    assert conflicts == []


def test_non_overlapping_weeks_never_conflict(credit_manager, make_course):
    """Two courses on the same weekday but in different weeks never collide."""
    a = make_course("A", weekday=1, start_section=1, campus="东单", weeks=[1, 2])
    b = make_course("B", weekday=1, start_section=3, campus="清华", weeks=[5, 6])

    conflicts = _conflicts(
        [a, b], credit_manager, mode=CampusConflictMode.PERIOD, min_transfer=8
    )

    assert conflicts == []


def test_disabled_mode_short_circuits(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, campus="东单")
    b = make_course("B", weekday=1, start_section=7, campus="清华")

    conflicts = _conflicts(
        [a, b], credit_manager, mode=CampusConflictMode.DISABLED, min_transfer=8
    )

    assert conflicts == []


def test_daily_mode_rejects_any_cross_campus_day(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, campus="东单")
    b = make_course("B", weekday=1, start_section=9, campus="清华")

    conflicts = _conflicts(
        [a, b], credit_manager, mode=CampusConflictMode.DAILY, min_transfer=0
    )

    assert len(conflicts) >= 1
    assert conflicts[0].conflict_type == "campus"


def test_different_weekdays_do_not_require_transfer_time(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, campus="东单")
    b = make_course("B", weekday=3, start_section=1, campus="清华")

    conflicts = _conflicts(
        [a, b], credit_manager, mode=CampusConflictMode.PERIOD, min_transfer=8
    )

    assert conflicts == []


def test_conflict_message_reports_the_gap_and_requirement(credit_manager, make_course):
    east = make_course("A", weekday=1, start_section=1, campus="东单")
    west = make_course("B", weekday=1, start_section=7, campus="清华")

    conflicts = _conflicts(
        [east, west], credit_manager, mode=CampusConflictMode.PERIOD, min_transfer=6
    )

    assert len(conflicts) == 1
    description = conflicts[0].description
    assert "4" in description and "6" in description
