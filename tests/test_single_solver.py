"""Strategic item: exactly one solver implementation must remain.

The engine used to carry two solvers — a reachable backtracking search and an
unreachable, half-finished OR-Tools CP-SAT path that duplicated the same
constraint semantics. The CP-SAT scaffolding has been removed; these tests stop
it (or a hard OR-Tools dependency) from creeping back.
"""

import inspect

from core.scheduling.config import SchedulingConfig
from core.scheduling.engine import SchedulingEngine
from core.scheduling.models import ScheduleStatus

REMOVED_CP_SAT_MEMBERS = [
    "_build_model",
    "_add_constraints",
    "_add_time_conflict_constraints",
    "_add_campus_conflict_constraints",
    "_add_credit_constraints",
    "_add_daily_limit_constraints",
    "_set_objective",
    "_solve_model",
    "_group_courses_by_code",
]


def test_dead_cp_sat_members_are_gone():
    for name in REMOVED_CP_SAT_MEMBERS:
        assert not hasattr(SchedulingEngine, name), f"{name} came back"


def test_engine_module_does_not_import_ortools():
    """A hard ortools import also reintroduced a Windows DLL clash with pandas."""
    source = inspect.getsource(inspect.getmodule(SchedulingEngine))
    code_lines = [
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("ortools" in line for line in code_lines), code_lines


def test_solution_collector_is_gone():
    module = inspect.getmodule(SchedulingEngine)
    assert not hasattr(module, "SolutionCollector")
    assert not hasattr(module, "ORTOOLS_AVAILABLE")


def test_engine_constructs_without_ortools(credit_manager):
    """Construction used to raise ImportError when ortools was absent."""
    engine = SchedulingEngine(SchedulingConfig(), credit_manager())
    assert engine is not None


def test_backtracking_is_the_live_path(credit_manager, make_course):
    """A real schedule must come out of the backtracking search."""
    engine = SchedulingEngine(
        SchedulingConfig(max_solutions=1, max_solve_time_seconds=10),
        credit_manager(required=4.0),
    )
    courses = [
        make_course("A", weekday=1, start_section=3, credits=2.0),
        make_course("B", weekday=2, start_section=3, credits=2.0),
        make_course("C", weekday=3, start_section=3, credits=2.0),
    ]

    results = engine.generate_schedules(courses)

    assert results
    assert results[0].status in {ScheduleStatus.SUCCESS, ScheduleStatus.PARTIAL}
    assert results[0].selected_courses


def test_ortools_missing_event_is_gone():
    """The service no longer emits an event for a dependency it does not use."""
    import core.services.scheduling_service as svc

    assert "ortools_missing" not in inspect.getsource(svc)


def test_requirements_no_longer_pin_ortools():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    lines = [
        line.strip()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any(line.lower().startswith("ortools") for line in lines), lines
