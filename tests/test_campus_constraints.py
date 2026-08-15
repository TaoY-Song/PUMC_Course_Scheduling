"""PERIOD 模式按半天时段分块判定跨校区。

规则来自实际作息：转场能不能赶上，取决于两节课中间有没有午休 / 晚饭，
而不是隔了几节。节次编号是等距整数，表达不了这个断点——
1-2→3-4（课间 10 分钟）与 3-4→5-6（午休）在"空出节数"上都是 0。

所以判定依据是 config.half_day_blocks（默认 1-4 上午 / 5-8 下午 / 9-10 晚上）：
同一块内跨校区禁止，跨块允许。
"""

import pytest

from core.scheduling.config import CampusConflictMode, SchedulingConfig
from core.scheduling.constraints import ConstraintChecker
from core.scheduling.engine import SchedulingEngine


def _conflicts(courses, credit_manager, *, mode=CampusConflictMode.PERIOD):
    config = SchedulingConfig(campus_conflict_mode=mode)
    return ConstraintChecker(config, credit_manager()).check_campus_conflicts(courses)


@pytest.mark.parametrize(
    "sections_a,sections_b,should_conflict,reason",
    [
        ((1, 2), (3, 4), True, "同属上午，只有课间操，赶不上"),
        ((3, 4), (5, 6), False, "上午→下午，隔着午休"),
        ((5, 6), (7, 8), True, "同属下午，赶不上"),
        ((7, 8), (9, 10), False, "下午→晚上，隔着晚饭"),
        ((1, 2), (7, 8), False, "上午→下午，隔着午休"),
        ((1, 2), (9, 10), False, "上午→晚上，时间充裕"),
        ((3, 4), (1, 2), True, "顺序颠倒也应同结果"),
    ],
)
def test_period_mode_uses_half_day_blocks(
    credit_manager, make_course, sections_a, sections_b, should_conflict, reason
):
    """逐条对齐真实作息规则。"""
    a = make_course(
        "A", weekday=1, start_section=sections_a[0], end_section=sections_a[1], campus="东单"
    )
    b = make_course(
        "B", weekday=1, start_section=sections_b[0], end_section=sections_b[1], campus="西院"
    )

    conflicts = _conflicts([a, b], credit_manager)

    assert bool(conflicts) is should_conflict, (
        f"{sections_a} vs {sections_b} 应{'禁止' if should_conflict else '允许'}：{reason}"
    )


def test_search_and_validation_agree_on_the_same_pair(credit_manager, make_course):
    """搜索期与校验期必须同口径。

    历史 bug：搜索期把转场冲突当硬约束拒掉，校验期却因 severity=medium
    放过，导致同一组课在两个阶段结论相反。
    """
    config = SchedulingConfig(campus_conflict_mode=CampusConflictMode.PERIOD)
    checker = ConstraintChecker(config, credit_manager())
    engine = SchedulingEngine(config, credit_manager(required=2.0))

    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=1, start_section=3, end_section=4, campus="西院")

    search_accepts = engine._is_campus_compatible(b, [a])
    validation_ok = checker.is_valid_schedule([a, b])

    assert search_accepts is False, "搜索期应拒绝同一时段的跨校区"
    assert validation_ok is False, "校验期必须同样判为无效（severity 需为 high）"


def test_conflict_is_a_hard_constraint(credit_manager, make_course):
    """同时段跨校区是物理上做不到的事，必须是 high。"""
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=1, start_section=3, end_section=4, campus="西院")

    conflicts = _conflicts([a, b], credit_manager)

    assert len(conflicts) == 1
    assert conflicts[0].severity == "high"
    assert conflicts[0].conflict_type == "campus"


def test_course_spanning_two_blocks_conflicts_with_both(credit_manager, make_course):
    """4-5 节横跨午休，它同时占上午和下午两块。"""
    spanning = make_course("S", weekday=1, start_section=4, end_section=5, campus="东单")
    morning = make_course("M", weekday=1, start_section=1, end_section=2, campus="西院")
    afternoon = make_course("A", weekday=1, start_section=7, end_section=8, campus="西院")
    evening = make_course("E", weekday=1, start_section=9, end_section=10, campus="西院")

    assert _conflicts([spanning, morning], credit_manager), "应与上午冲突"
    assert _conflicts([spanning, afternoon], credit_manager), "应与下午冲突"
    assert _conflicts([spanning, evening], credit_manager) == [], "与晚上无交集"


def test_custom_blocks_change_the_verdict(credit_manager, make_course):
    """作息不同的学校改 half_day_blocks 即可，不必动约束逻辑。"""
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=1, start_section=3, end_section=4, campus="西院")

    # 把上午拆成两块 → 1-2 与 3-4 不再同块 → 允许
    config = SchedulingConfig(
        campus_conflict_mode=CampusConflictMode.PERIOD,
        half_day_blocks=(("第一段", 1, 2), ("第二段", 3, 4), ("下午", 5, 8), ("晚上", 9, 10)),
    )
    conflicts = ConstraintChecker(config, credit_manager()).check_campus_conflicts([a, b])

    assert conflicts == []


def test_same_campus_never_conflicts(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=1, start_section=3, end_section=4, campus="东单")

    assert _conflicts([a, b], credit_manager) == []


def test_non_overlapping_weeks_never_conflict(credit_manager, make_course):
    """同一天同一时段，但周次不相交 → 人不会同时出现在两地。"""
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单", weeks=[1, 2])
    b = make_course("B", weekday=1, start_section=3, end_section=4, campus="西院", weeks=[5, 6])

    assert _conflicts([a, b], credit_manager) == []


def test_different_weekdays_never_conflict(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=3, start_section=3, end_section=4, campus="西院")

    assert _conflicts([a, b], credit_manager) == []


def test_disabled_mode_short_circuits(credit_manager, make_course):
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=1, start_section=3, end_section=4, campus="西院")

    assert _conflicts([a, b], credit_manager, mode=CampusConflictMode.DISABLED) == []


def test_daily_mode_rejects_cross_campus_even_across_blocks(credit_manager, make_course):
    """DAILY 比 PERIOD 严格：连跨块也不允许。"""
    a = make_course("A", weekday=1, start_section=1, end_section=2, campus="东单")
    b = make_course("B", weekday=1, start_section=9, end_section=10, campus="西院")

    period = _conflicts([a, b], credit_manager, mode=CampusConflictMode.PERIOD)
    daily = _conflicts([a, b], credit_manager, mode=CampusConflictMode.DAILY)

    assert period == [], "PERIOD 下上午→晚上可转场"
    assert len(daily) >= 1, "DAILY 下同一天不允许任何跨校区"
    assert daily[0].conflict_type == "campus"


def test_conflict_message_names_the_shared_block(credit_manager, make_course):
    """报错要说清是哪一段撞了，否则用户不知道怎么改。"""
    a = make_course("A", weekday=1, start_section=5, end_section=6, campus="东单")
    b = make_course("B", weekday=1, start_section=7, end_section=8, campus="西院")

    conflicts = _conflicts([a, b], credit_manager)

    assert len(conflicts) == 1
    description = conflicts[0].description
    assert "下午" in description, description
    assert "东单" in description and "西院" in description
