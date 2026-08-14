"""P0/P2: config validation, unit consistency, and stable result IDs."""

import pytest

from core.scheduling.config import (
    CampusConflictMode,
    CreditConstraintMode,
    SchedulingConfig,
)


def test_validate_runs_without_attribute_errors():
    """validate() referenced fields that did not exist on the dataclass."""
    assert SchedulingConfig().validate() == []


def test_validate_reports_bad_values():
    errors = SchedulingConfig(
        min_campus_transfer_time=-1,
        max_credit_overflow_ratio=2.0,
        max_solve_time_seconds=0,
        max_solutions=0,
    ).validate()

    assert len(errors) == 4


def test_time_preference_score_is_callable():
    """get_time_preference_score() raised AttributeError before the fix."""
    config = SchedulingConfig()
    assert 0.0 < config.get_time_preference_score(3) <= 1.0


@pytest.mark.parametrize(
    "factory,attr,expected",
    [
        ("get_default_config", "max_solutions", 100),
        ("get_strict_config", "max_credit_overflow_ratio", 0.1),
        ("get_flexible_config", "max_credit_overflow_ratio", 0.3),
    ],
)
def test_preset_factories_are_static(factory, attr, expected):
    """These were instance methods missing self, so calling them raised TypeError."""
    config = getattr(SchedulingConfig, factory)()
    assert getattr(config, attr) == expected


def test_config_dict_roundtrip_preserves_every_field():
    original = SchedulingConfig(
        campus_conflict_mode=CampusConflictMode.PERIOD,
        credit_constraint_mode=CreditConstraintMode.REQUIRED,
        min_campus_transfer_time=3,
        max_credit_overflow_ratio=0.25,
        avoid_early_morning=True,
        avoid_late_evening=True,
        lunch_break_protection=True,
        max_solve_time_seconds=45,
        max_solutions=7,
    )

    restored = SchedulingConfig.from_dict(original.to_dict())

    assert restored.to_dict() == original.to_dict()
    assert restored.avoid_early_morning is True
    assert restored.lunch_break_protection is True


def test_campus_transition_dto_uses_sections_not_minutes():
    """The DTO advertised minutes (0-120) but fed a sections-based core field."""
    from web_backend.models.dto import SchedulingConfigDTO

    field = SchedulingConfigDTO.model_fields["campus_transition_time"]
    constraints = {c.__class__.__name__: c for c in field.metadata}

    assert field.default == 2, "default should be a plausible section count"
    upper = next(
        getattr(c, "le") for c in field.metadata if hasattr(c, "le")
    )
    assert upper == 10, "a 120-section transfer window is not meaningful"


def test_selected_course_ids_are_stable_across_serialisations(make_course):
    """IDs used to be fresh uuid4()s, remounting the React list on every GET."""
    from web_backend.api.courses import _selected_course_to_dto

    course = make_course("PHYS101")

    first = _selected_course_to_dto(course).id
    second = _selected_course_to_dto(course).id

    assert first == second
    assert "PHYS101" in first


def test_distinct_courses_get_distinct_ids(make_course):
    from web_backend.api.courses import _selected_course_to_dto

    a = _selected_course_to_dto(make_course("PHYS101")).id
    b = _selected_course_to_dto(make_course("CHEM202")).id

    assert a != b


def test_explicit_selected_id_still_wins(make_course):
    from web_backend.api.courses import _selected_course_to_dto

    dto = _selected_course_to_dto(make_course("PHYS101"), "session-scoped-id")

    assert dto.id == "session-scoped-id"
