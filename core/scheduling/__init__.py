#!/usr/bin/env python3
"""
排课算法模块
基于OR-Tools CP-SAT求解器实现智能排课功能
"""

from .config import SchedulingConfig, CampusConflictMode, CreditConstraintMode
from .constraints import ConstraintChecker
from .engine import SchedulingEngine
from .evaluator import ScheduleEvaluator
from .models import ScheduleResult, ScheduleScore

__all__ = [
    "SchedulingConfig",
    "CampusConflictMode",
    "CreditConstraintMode",
    "ConstraintChecker",
    "SchedulingEngine",
    "ScheduleEvaluator",
    "ScheduleResult",
    "ScheduleScore",
]
