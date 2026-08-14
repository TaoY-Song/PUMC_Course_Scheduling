"""P0-4a / P0-4b: solution ranking and the solve time limit on the active path."""

from itertools import combinations
import random
import time

import pytest

from core.scheduling.config import CreditConstraintMode, SchedulingConfig
from core.scheduling.engine import SchedulingEngine
from core.scheduling.models import ScheduleStatus


def _grid(make_course, count):
    """Courses spread over weekdays/sections so many combinations are feasible."""
    return [
        make_course(f"C{i}", weekday=(i % 5) + 1, start_section=1 + 2 * (i // 5))
        for i in range(count)
    ]


def test_single_solution_is_the_best_not_the_first_feasible(
    credit_manager, make_course
):
    """max_solutions=1 must return the highest-scoring schedule.

    The backtracker stops at the first feasible solution. With a cap of 1 that
    used to leak straight through: a strictly better schedule (more courses,
    same constraints, higher score) existed but was never searched, so users
    always got the first greedy hit. The engine now searches a candidate pool
    and ranks before truncating.
    """
    # One course per weekday keeps every combination conflict-free, so the
    # richest schedule is also the best-scoring one.
    courses = [
        make_course(f"C{i}", weekday=i + 1, start_section=1, end_section=4, credits=1.0)
        for i in range(5)
    ]

    engine = SchedulingEngine(
        SchedulingConfig(max_solutions=1, max_solve_time_seconds=60),
        credit_manager(required=2.0),
    )
    best = engine.generate_schedules(courses)
    assert len(best) == 1

    pool = SchedulingEngine(
        SchedulingConfig(max_solutions=8, max_solve_time_seconds=60),
        credit_manager(required=2.0),
    ).generate_schedules(courses)

    # Nothing in the wider search may beat the single returned schedule.
    assert best[0].score.total_score == max(r.score.total_score for r in pool)


def test_multiple_solutions_are_deduplicated_and_score_ordered(
    credit_manager, make_course
):
    """Backtracking re-emits the same course set via different paths."""
    courses = [
        make_course(f"C{i}", weekday=i + 1, start_section=1, end_section=4, credits=1.0)
        for i in range(5)
    ]

    results = SchedulingEngine(
        SchedulingConfig(max_solutions=5, max_solve_time_seconds=60),
        credit_manager(required=2.0),
    ).generate_schedules(courses)

    signatures = [
        tuple(sorted((sc.course.code, sc.class_num) for sc in result.selected_courses))
        for result in results
    ]
    assert len(signatures) == len(set(signatures)), signatures

    scores = [result.score.total_score for result in results]
    assert scores == sorted(scores, reverse=True), scores


def test_small_required_schedules_match_an_exhaustive_oracle(
    credit_manager, make_course
):
    """固定随机种子的差分测试：小规模求解结果必须等于穷举最高分。"""
    randomizer = random.Random(20260328)

    for case_index in range(40):
        course_count = randomizer.randint(4, 8)
        courses = [
            make_course(
                f"R{case_index}-{index}",
                weekday=randomizer.randint(1, 4),
                start_section=randomizer.choice([1, 3, 5, 7]),
                credits=randomizer.choice([0.5, 1.0, 1.5, 2.0]),
            )
            for index in range(course_count)
        ]
        required = randomizer.choice([1.0, 1.5, 2.0, 2.5, 3.0])
        manager = credit_manager(required=required)
        config = SchedulingConfig(
            max_solutions=1,
            max_solve_time_seconds=10,
            credit_constraint_mode=CreditConstraintMode.REQUIRED,
            max_credit_overflow_ratio=1.0,
        )
        engine = SchedulingEngine(config, manager)

        results = engine.generate_schedules(courses)
        candidates = []
        for size in range(course_count + 1):
            for candidate in combinations(courses, size):
                occupied = set()
                compatible = True
                for course in candidate:
                    keys = set(engine._time_slot_keys(course))
                    if occupied & keys:
                        compatible = False
                        break
                    occupied.update(keys)
                credits = sum(course.course.credits for course in candidate)
                if (
                    compatible
                    and required <= credits <= required * 2
                ):
                    candidates.append(list(candidate))

        if not candidates:
            assert results == [], case_index
            continue

        result = results[0]
        expected_score = max(
            engine.evaluator.evaluate_schedule(candidate, manager, config).total_score
            for candidate in candidates
        )
        assert result.score.total_score == pytest.approx(expected_score), case_index


@pytest.mark.parametrize("cap", [1, 2, 5])
def test_engine_never_returns_more_than_max_solutions(
    credit_manager, make_course, cap
):
    """The backtracker had four append sites but only checked the cap at two."""
    engine = SchedulingEngine(
        SchedulingConfig(max_solutions=cap, max_solve_time_seconds=60),
        credit_manager(required=4.0),
    )

    results = engine.generate_schedules(_grid(make_course, 12))

    assert len(results) <= cap


def test_raising_max_solutions_yields_more_schedules(credit_manager, make_course):
    courses = _grid(make_course, 12)
    one = SchedulingEngine(
        SchedulingConfig(max_solutions=1, max_solve_time_seconds=60),
        credit_manager(required=4.0),
    ).generate_schedules(courses)
    five = SchedulingEngine(
        SchedulingConfig(max_solutions=5, max_solve_time_seconds=60),
        credit_manager(required=4.0),
    ).generate_schedules(courses)

    assert len(five) > len(one)


@pytest.mark.slow
def test_unreachable_target_stops_at_the_time_limit(credit_manager, make_course):
    """P0-4b: the active backtracking path had no time limit at all.

    A 100-credit target built from 0.5-credit courses is unreachable, so the
    backtracker must explore the whole space — previously unbounded, now cut off
    by max_solve_time_seconds.
    """
    courses = [
        make_course(
            f"H{i}",
            weekday=(i % 5) + 1,
            start_section=1 + 2 * ((i // 5) % 5),
            credits=0.5,
        )
        for i in range(30)
    ]
    engine = SchedulingEngine(
        SchedulingConfig(
            max_solutions=10**9,
            max_solve_time_seconds=1,
            credit_constraint_mode=CreditConstraintMode.REQUIRED,
        ),
        credit_manager(required=100.0),
    )

    started = time.monotonic()
    results = engine.generate_schedules(courses)
    elapsed = time.monotonic() - started

    assert engine._timed_out is True
    assert elapsed < 15, f"search ran {elapsed:.1f}s despite a 1s limit"
    # A timeout with no feasible solution must still report itself, not return [].
    assert len(results) == 1
    assert results[0].status is ScheduleStatus.TIMEOUT
    assert any("时间上限" in w for w in results[0].warnings)


def test_zero_time_limit_disables_the_deadline(credit_manager, make_course):
    """max_solve_time_seconds<=0 means 'no limit', not 'stop immediately'."""
    engine = SchedulingEngine(
        SchedulingConfig(max_solutions=1, max_solve_time_seconds=0),
        credit_manager(required=2.0),
    )

    results = engine.generate_schedules(_grid(make_course, 6))

    assert engine._timed_out is False
    assert results  # still produced a schedule


def test_timed_out_flag_resets_between_runs(credit_manager, make_course):
    """A stale _timed_out would wrongly mark later successful runs as TIMEOUT."""
    engine = SchedulingEngine(
        SchedulingConfig(max_solutions=1, max_solve_time_seconds=60),
        credit_manager(required=2.0),
    )
    engine._timed_out = True  # simulate a previous timed-out run

    results = engine.generate_schedules(_grid(make_course, 6))

    assert engine._timed_out is False
    assert results[0].status is not ScheduleStatus.TIMEOUT
