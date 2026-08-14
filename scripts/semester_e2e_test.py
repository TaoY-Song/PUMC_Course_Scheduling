#!/usr/bin/env python3
"""构造一个学期的真实目录测试场景，并验证 FastAPI/WebSocket 排课链路。"""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_backend.server import app  # noqa: E402

CAMPUSES = ("东单校区", "北礼士路校区", "院校北区")
# 每天固定一个校区：DAILY 模式下同一天跳校区必然判冲突，
# 所以按天预绑校区，让“无冲突”由构造保证，而不是靠碍撞重试。
DAY_CAMPUS = {day: CAMPUSES[(day - 1) % len(CAMPUSES)] for day in range(1, 6)}
# 一节课 4 小时 = 4 个节次：上午 1-4 节，下午 5-8 节。
BLOCK_STARTS = (1, 5)
CATEGORY_BY_SOURCE = {
    "公共必修课": "公共必修课 - 公共必修",
    "通识选修课": "选修课 - 通识选修",
    "限制选修课": "选修课 - 限制性选修",
    "学位专业课": "学位必修课（核心课）",
    "学位必修课": "学位必修课（核心课）",
    "学位选修课": "选修课 - 学位选修",
}
# 每个目标类别 ← 可用的源表类别标签（fixture 写源标签，让 loader 正常规范化）
SOURCE_LABELS_FOR_TARGET = {
    "公共必修课 - 公共必修": ("公共必修课",),
    "公共必修课 - 公共必修（二选一）": ("公共必修课",),
    "选修课 - 通识选修": ("通识选修课",),
    "选修课 - 限制性选修": ("限制选修课",),
    "选修课 - 学位选修": ("学位选修课",),
    "学位必修课（核心课）": ("学位必修课", "学位专业课"),
}
# 期望的各类别学分目标（模拟一个学期的真实培养方案缺口）。
# 时段池只有 10 格（5 天 x 上/下午），所以总量控制在 6-7 门。
DESIRED_TARGETS = {
    "公共必修课 - 公共必修": 2.0,
    "公共必修课 - 公共必修（二选一）": 1.0,
    "选修课 - 通识选修": 1.0,
    "选修课 - 限制性选修": 1.5,
    "选修课 - 学位选修": 2.0,
    "学位必修课（核心课）": 3.0,
}
HARD_CONFLICT_KEYS = ("time", "campus")


def normalized_category(raw: Any) -> str:
    text = str(raw or "").strip()
    return CATEGORY_BY_SOURCE.get(text, "选修课 - 学位选修")


def meetings_for(credits: float, hours: float) -> tuple[int, int]:
    """返回每周次数与授课周数；每次 4 节，按总学时向上取整。"""
    meetings = 2 if credits >= 3.0 or hours >= 48 else 1
    weeks = max(4, min(18, math.ceil(max(hours, credits * 16, 16) / (meetings * 4))))
    return meetings, weeks


def plan_courses(frame: pd.DataFrame) -> list[tuple[pd.Series, str, str]]:
    """按“每类别学分目标”选课，返回 (源行, 源类别标签, 意图规范类别)。

    之前的 pick_courses 只按学分降序拉课，导致大部分类别根本没课，
    学分匹配分必然偏低（学期2/3 只服 36-46 分）。现在改为类别感知：
    逐类别凑到目标学分，优先选不超额的最大学分课（减少溢出惩罚）。
    源表没有“课程类别”列时（学期2），确定性分派类别——用户已授权虚构。
    """
    valid = frame[
        frame["课程编码"].notna()
        & frame["课程名称"].notna()
        & pd.to_numeric(frame["学分"], errors="coerce").fillna(0).gt(0)
    ].copy()
    valid["_credits"] = pd.to_numeric(valid["学分"], errors="coerce").fillna(0.0)
    has_category = "课程类别" in valid.columns
    if has_category:
        valid["_source_category"] = valid["课程类别"].astype(str).str.strip()

    planned: list[tuple[pd.Series, str, str]] = []
    used_codes: set[str] = set()

    for target_category, desired in DESIRED_TARGETS.items():
        source_labels = SOURCE_LABELS_FOR_TARGET[target_category]
        if has_category:
            candidates = valid[valid["_source_category"].isin(source_labels)]
        else:
            # 无类别列：从全量课程里分派，写入第一个源标签
            candidates = valid
        # 优先不超额的最大学分，其次最小超额
        candidates = candidates.assign(
            _fit=lambda df: df["_credits"].apply(lambda c: (c > desired, abs(desired - c)))
        ).sort_values("_fit")

        accumulated = 0.0
        for _, row in candidates.iterrows():
            if accumulated >= desired:
                break
            code = str(row["课程编码"]).strip()
            if code in used_codes:
                continue
            used_codes.add(code)
            planned.append((row, source_labels[0], target_category))
            accumulated += float(row["_credits"])

    return planned


def build_fixture(source: Path, output: Path) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, float]]:
    """构造一个学期的待选课：每次课 4 节（上午或下午），高学分排两次。

    时段池是有限的（5 天 x 2 个块），所以采用确定性预分配：
    按“校区 -> 该校区名下的可用(天,起始节)”建池，不够就停止收课。
    之前的实现用无界 while 重试碰撞，当某校区可用天被占满时会死循环。

    返回 (fixture 行, "编码#班次"->意图类别, 有效学分目标)。
    有效目标从实际落位的行反推，保证目标可达（不会凭空报缺口）。
    """
    frame = pd.read_excel(source)

    # 每个校区的可用时段池（确定顺序，便于复现）
    pools: dict[str, list[tuple[int, int]]] = {campus: [] for campus in CAMPUSES}
    for start in BLOCK_STARTS:
        for day in sorted(DAY_CAMPUS):
            pools[DAY_CAMPUS[day]].append((day, start))

    rows: list[dict[str, Any]] = []
    intended_by_code: dict[str, str] = {}
    supplied: dict[str, float] = {}

    for index, (source_row, source_label, intended_category) in enumerate(plan_courses(frame)):
        credits = float(source_row.get("学分", 1) or 1)
        hours = float(source_row.get("学时", credits * 16) or credits * 16)
        meetings, weeks = meetings_for(credits, hours)
        campus = CAMPUSES[index % len(CAMPUSES)]

        # 两次课必须落在同校区的不同天，池不够就降为一次，再不够就不收这门课。
        pool = pools[campus]
        distinct_days = {slot[0] for slot in pool}
        if meetings == 2 and len(distinct_days) < 2:
            meetings = 1
        if not pool:
            continue

        chosen: list[tuple[int, int]] = []
        used_days: set[int] = set()
        for _ in range(meetings):
            candidate = next((slot for slot in pool if slot[0] not in used_days), None)
            if candidate is None:
                break
            pool.remove(candidate)
            used_days.add(candidate[0])
            chosen.append(candidate)
        if not chosen:
            continue

        code = str(source_row["课程编码"]).strip()
        class_index = int(pd.to_numeric(source_row.get("班次", 1), errors="coerce") or 1)
        row = {
            "课程编码": code,
            "课程名称": str(source_row["课程名称"]).strip(),
            "开课院系": str(source_row.get("开课院系", "研究生院")).strip(),
            # 写源类别标签（如“限制选修课”），让 loader/SelectedCourse 走真实规范化路径；
            # 之前直接写规范化名会让自动推断落错桶。
            "课程类别": source_label,
            "班次": class_index,
            "校区": campus,
            "任课教师": str(source_row.get("任课教师", "待定")).strip(),
            "学分": credits,
            "学时": hours,
            "选课说明": "自动构造的单学期端到端测试数据",
        }
        for meeting, (day, start) in enumerate(chosen):
            suffix = "" if meeting == 0 else "2"
            row[f"星期{suffix}"] = day
            row[f"开始节次{suffix}"] = start
            row[f"结束节次{suffix}"] = start + 3
            row[f"周次{suffix}"] = f"1-{weeks}"
        rows.append(row)
        intended_by_code[f"{code}#{class_index}"] = intended_category
        supplied[intended_category] = supplied.get(intended_category, 0.0) + credits

    if not rows:
        raise SystemExit("无法构造任何待选课程，请检查源数据")

    # 有效目标 = min(期望, 实际可供)；一门课都没落位的类别目标置 0。
    # /api/credits/settings 是增量语义，所以默认类别必须全部显式列出。
    effective_targets = {
        category: round(min(desired, supplied.get(category, 0.0)), 1)
        for category, desired in DESIRED_TARGETS.items()
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(output, index=False)
    return rows, intended_by_code, effective_targets


def run_api_scenario(source: Path, fixture: Path, report_path: Path) -> dict[str, Any]:
    fixture_rows, intended_by_code, targets = build_fixture(source, fixture)
    report: dict[str, Any] = {
        "source_semester": source.name,
        "fixture": str(fixture.relative_to(ROOT)),
        "input_courses": len(fixture_rows),
        "credit_targets": targets,
        "courses": [],
        "websocket_events": [],
    }

    with TestClient(app) as client:
        with fixture.open("rb") as handle:
            loaded_response = client.post(
                "/api/courses/load",
                files={"file": (fixture.name, handle, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        loaded_response.raise_for_status()
        loaded = loaded_response.json()
        assert loaded["success"] and loaded["course_count"] == len(fixture_rows)
        assert all(course["time_slots"] for course in loaded["courses"])

        selected = []
        for course in loaded["courses"]:
            response = client.post(
                "/api/selected-courses",
                data={"course_code": course["course_code"], "class_index": course["class_index"]},
            )
            response.raise_for_status()
            selected.append(response.json())

        # 把类别对齐到意图值（等价于课程页的类别下拉选择）。
        # 公共必修课会被规范化为 "nan"（设计上强制用户手选），
        # “二选一”这种细分也只能用户指定，所以用 PATCH 统一回放。
        patched_count = 0
        normalized: list[dict[str, Any]] = []
        for course in selected:
            key = f"{course['course']['course_code']}#{course['class_index']}"
            intended = intended_by_code.get(key)
            current = str(course.get("custom_category", "")).strip()
            if intended and current != intended:
                patched = client.patch(
                    f"/api/selected-courses/{course['id']}",
                    json={"custom_category": intended},
                )
                patched.raise_for_status()
                normalized.append(patched.json())
                patched_count += 1
            else:
                normalized.append(course)
        selected = normalized
        report["category_patched"] = patched_count
        assert all(
            str(course["custom_category"]).strip().lower() not in {"", "nan"} for course in selected
        )

        credit_response = client.post("/api/credits/settings", json=targets)
        credit_response.raise_for_status()
        config_response = client.post(
            "/api/scheduling/config",
            json={
                "credit_constraint_mode": "OPTIMAL",
                "campus_conflict_mode": "DAILY",
                "max_solutions": 1,
                "time_limit": 30,
                "credit_overflow_ratio": 0.5,
                "campus_transition_time": 2,
            },
        )
        config_response.raise_for_status()

        events: list[dict[str, Any]] = []
        final_status: dict[str, Any] | None = None

        # WebSocket 必须在提交任务前订阅，否则会漏掉 started 事件。
        # Starlette 的 receive_json() 没有超时参数，所以放到守护线程里读，
        # 主线程用 HTTP 状态轮询决定何时收口。
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "action": "subscribe",
                    "event_types": [
                        "scheduling.started",
                        "scheduling.progress",
                        "scheduling.completed",
                        "scheduling.failed",
                    ],
                }
            )
            assert websocket.receive_json()["type"] == "subscribed"

            def drain() -> None:
                while True:
                    try:
                        events.append(websocket.receive_json())
                    except Exception:
                        return

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()

            execute_response = client.post(
                "/api/scheduling/execute",
                json={"course_ids": [course["id"] for course in selected]},
            )
            execute_response.raise_for_status()
            task_id = execute_response.json()["task_id"]

            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                status_response = client.get(f"/api/scheduling/status/{task_id}")
                status_response.raise_for_status()
                final_status = status_response.json()
                if final_status["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.1)
            # 给事件循环一点时间把尾部事件推完
            time.sleep(0.5)

        assert final_status is not None
        assert final_status["status"] == "completed", final_status
        result = final_status.get("result")
        assert result and result["selected_courses"]
        assert all(course["time_slots"] for course in result["selected_courses"] if not course["is_online"])

        # 硬约束（时间/校区冲突）必须为空；OPTIMAL 模式下的学分缺口
        # 是优化提示，单独报告而不当作失败。
        hard_conflicts = [
            conflict
            for conflict in result["conflicts"]
            if any(key in str(conflict["conflict_type"]).lower() for key in HARD_CONFLICT_KEYS)
        ]
        credit_conflicts = [
            conflict for conflict in result["conflicts"] if conflict not in hard_conflicts
        ]
        assert hard_conflicts == [], hard_conflicts

        # 结果内部也不得有重叠时段 / 同天跳校区
        occupied: dict[tuple[int, int], str] = {}
        day_campus: dict[int, set[str]] = {}
        for course in result["selected_courses"]:
            for slot in course["time_slots"]:
                for period in range(slot["start_period"], slot["end_period"] + 1):
                    key = (slot["day_of_week"], period)
                    assert key not in occupied, (key, occupied[key], course["course"]["course_code"])
                    occupied[key] = course["course"]["course_code"]
                day_campus.setdefault(slot["day_of_week"], set()).add(
                    course["course"]["campus"] or ""
                )
        cross_campus_days = {day: sorted(names) for day, names in day_campus.items() if len(names) > 1}
        assert cross_campus_days == {}, cross_campus_days

        export_response = client.get("/api/scheduling/result")
        export_response.raise_for_status()
        assert export_response.json()["id"] == result["id"]

        # 任务隔离：每个下发事件都必须带当前 task_id
        event_task_ids = {
            event.get("data", {}).get("task_id")
            for event in events
            if isinstance(event.get("data"), dict)
        }
        assert event_task_ids <= {task_id}, event_task_ids
        assert any(event.get("type") == "scheduling.completed" for event in events), [
            event.get("type") for event in events
        ]

        # 学分达成：目标已根据实际可供量收敛，所以不应再有缺口。
        credit_rows = client.get("/api/credits").json()
        credit_status = {
            row["category"]: {
                "required": row["required_credits"],
                "completed": row["completed_credits"],
                "remaining": row["remaining_credits"],
                "is_completed": row["is_completed"],
            }
            for row in credit_rows
            if row["required_credits"] > 0 or row["completed_credits"] > 0
        }
        unmet = {
            category: data
            for category, data in credit_status.items()
            if data["required"] > 0 and not data["is_completed"]
        }

        report.update(
            {
                "loaded_count": loaded["course_count"],
                "selected_count": len(selected),
                "task_id": task_id,
                "task_status": final_status["status"],
                "task_percent": final_status["percent"],
                "result_courses": len(result["selected_courses"]),
                "score": result["score"],
                "hard_conflicts": hard_conflicts,
                "credit_gap_notes": [conflict["description"] for conflict in credit_conflicts],
                "credit_status": credit_status,
                "unmet_categories": unmet,
                "occupied_periods": len(occupied),
                "cross_campus_days": cross_campus_days,
                "websocket_events": [event.get("type") for event in events],
                "websocket_task_ids": sorted(
                    {
                        str(event.get("data", {}).get("task_id"))
                        for event in events
                        if isinstance(event.get("data"), dict)
                    }
                ),
                "courses": [
                    {
                        "code": course["course"]["course_code"],
                        "name": course["course"]["course_name"],
                        "credits": course["course"]["credits"],
                        "category": course["custom_category"],
                        "campus": course["course"]["campus"],
                        "time_slots": course["time_slots"],
                    }
                    for course in result["selected_courses"]
                ],
            }
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semester", type=int, default=2, choices=(1, 2, 3))
    args = parser.parse_args()
    sources = sorted((ROOT / "test_data").glob("*.xls*"))
    if len(sources) != 3:
        raise SystemExit(f"预期 3 个学期文件，实际找到 {len(sources)} 个")
    source = sources[args.semester - 1]
    fixture = ROOT / "test_data" / "generated" / f"semester_{args.semester}_selected_courses.xlsx"
    report_path = ROOT / "test_data" / "generated" / f"semester_{args.semester}_e2e_result.json"
    report = run_api_scenario(source, fixture, report_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    print("\n=== VERDICT ===")
    print(f"source={report['source_semester']}")
    print(f"targets={report['credit_targets']}")
    print(
        f"loaded={report['loaded_count']} selected={report['selected_count']} "
        f"patched={report['category_patched']} result={report['result_courses']}"
    )
    print(f"status={report['task_status']} score={round(report['score']['total_score'], 2)}")
    print(f"credit_match={round(report['score']['credit_match_score'], 2)}")
    print(f"hard_conflicts={report['hard_conflicts']}")
    print(f"unmet_categories={report['unmet_categories']}")
    print(f"credit_gap_notes={report['credit_gap_notes']}")

    assert report["task_status"] == "completed"
    assert report["hard_conflicts"] == []
    assert report["cross_campus_days"] == {}
    assert report["unmet_categories"] == {}, report["unmet_categories"]
    assert report["credit_gap_notes"] == [], report["credit_gap_notes"]
    assert report["score"]["credit_match_score"] >= 90.0, report["score"]
    print("ALL_API_CHECKS_PASSED")


if __name__ == "__main__":
    main()
