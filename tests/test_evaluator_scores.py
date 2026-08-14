"""P1: score fields must be populated, bounded, and react to config."""

import pytest

from core.scheduling.config import SchedulingConfig
from core.scheduling.evaluator import ScheduleEvaluator


def _evaluate(courses, cm, config=None):
    config = config or SchedulingConfig()
    return ScheduleEvaluator(config).evaluate_schedule(courses, cm, config)


def test_all_score_fields_are_populated(credit_manager, make_course):
    """The original bug: only total_score and credit_efficiency_score were set."""
    cm = credit_manager(required=6.0)
    courses = [
        make_course("A", weekday=1, start_section=3, credits=2.0),
        make_course("B", weekday=2, start_section=3, credits=2.0),
        make_course("C", weekday=3, start_section=7, credits=2.0),
    ]

    score = _evaluate(courses, cm)

    assert score.total_score > 0
    assert score.time_preference_score > 0
    assert score.campus_consistency_score > 0
    assert score.course_distribution_score > 0
    assert score.credit_efficiency_score > 0


@pytest.mark.parametrize(
    "field",
    [
        "total_score",
        "time_preference_score",
        "campus_consistency_score",
        "course_distribution_score",
        "credit_efficiency_score",
    ],
)
def test_scores_stay_within_zero_to_hundred(credit_manager, make_course, field):
    """The dataclass documents 0-100; the old code could return 108."""
    cm = credit_manager(required=6.0)
    courses = [
        make_course("A", weekday=1, start_section=3, credits=2.0),
        make_course("B", weekday=2, start_section=3, credits=2.0),
        make_course("C", weekday=3, start_section=7, credits=2.0),
    ]

    score = _evaluate(courses, cm)

    value = getattr(score, field)
    assert 0.0 <= value <= 100.0, f"{field}={value}"


def test_cross_campus_lowers_consistency(credit_manager, make_course):
    cm = credit_manager(required=4.0)
    same = [
        make_course("A", weekday=1, start_section=3, campus="东单"),
        make_course("B", weekday=1, start_section=7, campus="东单"),
    ]
    cross = [
        make_course("A", weekday=1, start_section=3, campus="东单"),
        make_course("B", weekday=1, start_section=7, campus="清华"),
    ]

    assert (
        _evaluate(cross, cm).campus_consistency_score
        < _evaluate(same, cm).campus_consistency_score
    )


@pytest.mark.parametrize(
    "flag,start_section",
    [
        ("avoid_early_morning", 1),
        ("avoid_late_evening", 9),
        ("lunch_break_protection", 5),
    ],
)
def test_time_preference_flags_take_effect(
    credit_manager, make_course, flag, start_section
):
    """These config flags were previously ignored by the active scorer."""
    cm = credit_manager(required=2.0)
    courses = [make_course("A", weekday=1, start_section=start_section)]

    off = SchedulingConfig(**{flag: False})
    on = SchedulingConfig(**{flag: True})

    score_off = _evaluate(courses, cm, off).time_preference_score
    score_on = _evaluate(courses, cm, on).time_preference_score

    assert score_on < score_off, f"{flag} had no effect ({score_on} vs {score_off})"


def test_empty_schedule_scores_zero(credit_manager):
    score = _evaluate([], credit_manager(required=4.0))
    assert score.total_score == 0.0


def test_dto_exposes_the_real_time_quality_score(credit_manager, make_course):
    """The Web DTO read time_preference_score, which was always 0."""
    from web_backend.api.scheduling import _to_schedule_score_dto

    cm = credit_manager(required=4.0)
    courses = [make_course("A", weekday=1, start_section=3, credits=2.0)]
    score = _evaluate(courses, cm)

    dto = _to_schedule_score_dto(score)

    assert dto.time_quality_score == score.time_preference_score
    assert dto.time_quality_score > 0
