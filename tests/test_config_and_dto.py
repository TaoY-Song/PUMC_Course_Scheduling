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
        half_day_blocks=(("倒置", 5, 2),),
        max_credit_overflow=-1.0,
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
        ("get_strict_config", "max_credit_overflow", 0.5),
        ("get_flexible_config", "max_credit_overflow", 2.0),
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
        half_day_blocks=(("上午", 1, 4), ("下午", 5, 8)),
        max_credit_overflow=1.5,
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


def test_half_day_blocks_survive_dict_roundtrip():
    """时段划分是 PERIOD 模式的全部语义，序列化不能丢。"""
    original = SchedulingConfig(
        half_day_blocks=(("早", 1, 2), ("中", 3, 6), ("晚", 7, 10)),
    )

    restored = SchedulingConfig.from_dict(original.to_dict())

    assert restored.half_day_blocks == original.half_day_blocks


def test_period_knob_is_gone_from_the_dto():
    """旧的 campus_transition_time（“隔几节”）语义上表达不了作息断点。

    gap = 后一门.start - 前一门.end - 1 对下面三种情况全算 0：
      1-2 → 3-4（课间 10 分，赶不上）
      3-4 → 5-6（午休，赶得上）
      7-8 → 9-10（晚饭，赶得上）
    保留一个不生效的旋钮比删掉它更容易误导用户。
    """
    from web_backend.models.dto import SchedulingConfigDTO

    assert "campus_transition_time" not in SchedulingConfigDTO.model_fields


def test_overflow_dto_is_credits_not_ratio():
    """溢出上限是学分数，不是 0-1 的比例。

    比例制在小缺口上张不开：限选要求 1.0、ratio=0.2 时上限只 1.2，
    连一门 1.5 分的课都收不下，该类反而 0 学分。
    """
    from web_backend.models.dto import SchedulingConfigDTO

    assert "credit_overflow_ratio" not in SchedulingConfigDTO.model_fields
    field = SchedulingConfigDTO.model_fields["credit_overflow"]
    upper = next(getattr(c, "le") for c in field.metadata if hasattr(c, "le"))
    assert upper > 1.0, "上限应以学分为单位，能超过 1"


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
