"""P0-2 / P0-4c: credit gap arithmetic and the overflow-ratio setting."""

import pytest

from core.scheduling.config import SchedulingConfig
from core.scheduling.constraints import ConstraintChecker
from core.scheduling.engine import SchedulingEngine
from tests.conftest import ELECTIVE


def _bare_engine(config, credit_manager):
    """Build an engine without the OR-Tools constructor check.

    The credit-efficiency helper is pure Python; instantiating the full engine
    would only add an import guard that is irrelevant to these assertions.
    """
    engine = object.__new__(SchedulingEngine)
    engine.config = config
    engine.credit_manager = credit_manager
    engine._timed_out = False
    return engine


def test_gap_is_required_minus_completed(credit_manager):
    cm = credit_manager(required=8.0, completed=2.0)
    engine = _bare_engine(SchedulingConfig(), cm)

    gaps = engine._calculate_credit_requirements()

    assert gaps[ELECTIVE] == pytest.approx(6.0)


def test_completed_credits_are_not_subtracted_twice(credit_manager, make_course):
    """The original bug: base credits were counted against the gap again.

    required=8, completed=2 -> gap=6. With 4 new credits selected the student
    still needs 2 more, but the old code compared completed+selected (2+4=6)
    against the gap (6) and refused to add anything else.
    """
    cm = credit_manager(required=8.0, completed=2.0)
    engine = _bare_engine(SchedulingConfig(), cm)
    gaps = engine._calculate_credit_requirements()
    selected = [make_course(f"C{i}", weekday=(i % 5) + 1) for i in range(4)]

    allowed = engine._should_add_course_for_credit_efficiency(
        make_course("NEW"), selected, gaps
    )

    assert allowed is True


def test_final_credit_check_counts_completed_credits(credit_manager, make_course):
    """Regression: completed=2 plus six new credits satisfies required=8."""
    cm = credit_manager(required=8.0, completed=2.0)
    checker = ConstraintChecker(SchedulingConfig(), cm)
    courses = [make_course(f"C{i}", weekday=(i % 5) + 1) for i in range(6)]

    conflicts = checker.check_credit_constraints(courses)

    assert conflicts == []


def test_rejects_once_the_gap_is_filled(credit_manager, make_course):
    cm = credit_manager(required=8.0, completed=2.0)
    engine = _bare_engine(SchedulingConfig(), cm)
    gaps = engine._calculate_credit_requirements()
    selected = [make_course(f"C{i}", weekday=(i % 5) + 1) for i in range(6)]

    allowed = engine._should_add_course_for_credit_efficiency(
        make_course("NEW"), selected, gaps
    )

    assert allowed is False


def test_completed_plus_new_credits_reach_the_requirement(credit_manager, make_course):
    """Guards the arithmetic itself: 2 completed + 6 new == 8 required."""
    cm = credit_manager(required=8.0, completed=2.0)
    engine = _bare_engine(SchedulingConfig(), cm)
    gaps = engine._calculate_credit_requirements()

    selected = []
    for i in range(20):  # try to add far more than needed
        candidate = make_course(f"C{i}", weekday=(i % 5) + 1)
        if not engine._should_add_course_for_credit_efficiency(candidate, selected, gaps):
            break
        selected.append(candidate)

    new_credits = sum(c.course.credits for c in selected)
    completed = cm.get_requirement(ELECTIVE).completed_credits
    assert new_credits == pytest.approx(6.0)
    assert completed + new_credits == pytest.approx(8.0)


@pytest.mark.parametrize(
    "overflow,candidate_credits,expected",
    [
        (0.0, 3.0, False),  # 已选 2 + 3 = 5 > 缺口 4，无溢出额度
        (2.0, 3.0, True),   # 上限变为 4 + 2 = 6
        (0.0, 2.0, True),   # 刚好填满缺口
    ],
)
def test_overflow_limit_is_a_fixed_credit_amount(
    credit_manager, make_course, overflow, candidate_credits, expected
):
    """溢出上限是固定学分数，不是比例。

    比例制在小缺口上张不开：限选要求 1.0、ratio=0.2 时上限只 1.2，
    连一门 1.5 分的课都收不下；而培养方案只写下限、无上限。
    """
    cm = credit_manager(required=4.0)
    engine = _bare_engine(
        SchedulingConfig(max_credit_overflow=overflow, allow_credit_overflow=True), cm
    )
    selected = [make_course("A"), make_course("B", weekday=2)]  # 2 credits

    allowed = engine._should_add_course_for_credit_efficiency(
        make_course("CAND", credits=candidate_credits),
        selected,
        {ELECTIVE: 4.0},
    )

    assert allowed is expected


def test_empty_category_is_rescued_when_no_smaller_option_exists(
    credit_manager, make_course
):
    """该类一门未选且无替代时，允许突破溢出上限。

    真实案例：限制性选修要求 >=1.0，本学期唯一开的那门是 1.5 分。
    拒掉会使该类 0 学分——比溢出 0.5 分更不合培养方案（只规定下限）。
    """
    cm = credit_manager(required=1.0)
    engine = _bare_engine(
        SchedulingConfig(max_credit_overflow=0.0, rescue_empty_category=True), cm
    )
    only_option = make_course("ONLY", credits=1.5)

    allowed = engine._should_add_course_for_credit_efficiency(
        only_option, [], {ELECTIVE: 1.0}, category_pool=[only_option]
    )

    assert allowed is True


def test_rescue_does_not_fire_when_a_smaller_option_fits(credit_manager, make_course):
    """救场不得滥用：同类里有不超上限的课时，超限的仍应拒绝。

    否则回溯从空集开始时会直接放过大课，把正常的小课挤掉。
    """
    cm = credit_manager(required=2.0)
    engine = _bare_engine(
        SchedulingConfig(max_credit_overflow=0.5, rescue_empty_category=True), cm
    )
    too_big = make_course("BIG", credits=3.0)
    fits = make_course("FIT", credits=1.0, weekday=2)

    allowed = engine._should_add_course_for_credit_efficiency(
        too_big, [], {ELECTIVE: 2.0}, category_pool=[too_big, fits]
    )

    assert allowed is False


def test_rescue_can_be_disabled(credit_manager, make_course):
    cm = credit_manager(required=1.0)
    engine = _bare_engine(
        SchedulingConfig(max_credit_overflow=0.0, rescue_empty_category=False), cm
    )
    only_option = make_course("ONLY", credits=1.5)

    allowed = engine._should_add_course_for_credit_efficiency(
        only_option, [], {ELECTIVE: 1.0}, category_pool=[only_option]
    )

    assert allowed is False


def test_disallowing_overflow_forbids_exceeding_the_gap(credit_manager, make_course):
    cm = credit_manager(required=4.0)
    engine = _bare_engine(SchedulingConfig(allow_credit_overflow=False), cm)
    selected = [make_course("A"), make_course("B", weekday=2)]  # 2 credits

    allowed = engine._should_add_course_for_credit_efficiency(
        make_course("CAND", credits=3.0), selected, {ELECTIVE: 4.0}
    )

    assert allowed is False


def test_unknown_category_is_rejected(credit_manager, make_course):
    cm = credit_manager(required=4.0)
    engine = _bare_engine(SchedulingConfig(), cm)

    allowed = engine._should_add_course_for_credit_efficiency(
        make_course("X", category="不存在的类别"), [], {ELECTIVE: 4.0}
    )

    assert allowed is False
