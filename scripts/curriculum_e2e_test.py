#!/usr/bin/env python3
"""用真实培养方案数据集跑全栈测试（前端输入 → 后端输出）。

与 semester_e2e_test.py 的区别：那个是「6 门课刚好凑满」的理想化数据，
这里用 scripts/build_curriculum_dataset.py 生成的贴合培养方案的数据集，
覆盖三类真实特征：

* 博士 / 硕士两套不同学分要求，同一份课表结论必须不同
* 跨学期供给不足 —— OPTIMAL 给部分解并如实报缺口，REQUIRED 明确失败
* 不规则周次 + 例外时段（某几周换时段）端到端保真

用法：
    python scripts/curriculum_e2e_test.py --plan phd
    python scripts/curriculum_e2e_test.py --plan master --scarce
    python scripts/curriculum_e2e_test.py --all
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi TestClient unavailable")
from fastapi.testclient import TestClient  # noqa: E402

DEFAULT_CATEGORIES = [
    "公共必修课 - 公共必修",
    "公共必修课 - 公共必修（二选一）",
    "选修课 - 限制性选修",
    "选修课 - 通识选修",
    "选修课 - 学位选修",
    "学位必修课（核心课）",
]


def ensure_dataset(plan: str, scarce: bool) -> tuple[Path, dict[str, Any]]:
    """生成（或复用）数据集。直接调构建脚本，避免两份逻辑漂移。"""
    suffix = f"{plan}{'_scarce' if scarce else ''}"
    xlsx = ROOT / "test_data" / "generated" / f"curriculum_{suffix}.xlsx"
    meta_path = ROOT / "test_data" / "generated" / f"curriculum_{suffix}_meta.json"

    command = [sys.executable, str(ROOT / "scripts" / "build_curriculum_dataset.py"), "--plan", plan]
    if scarce:
        command.append("--scarce")
    subprocess.run(command, check=True, capture_output=True)

    if not xlsx.exists() or not meta_path.exists():
        raise SystemExit(f"数据集生成失败：{xlsx}")
    return xlsx, json.loads(meta_path.read_text(encoding="utf-8"))


def run_scenario(plan: str, scarce: bool, mode: str) -> dict[str, Any]:
    dataset, meta = ensure_dataset(plan, scarce)
    report: dict[str, Any] = {
        "plan": meta["plan_label"],
        "scarce": scarce,
        "credit_mode": mode,
        "dataset": dataset.name,
        "dataset_courses": meta["course_count"],
        "expected_gaps": meta["expected_gaps"],
    }

    with TestClient(app_client()) as client:
        # ── 1. 导入课表（等价于用户点「导入课程表」）──────────────────
        with dataset.open("rb") as handle:
            loaded = client.post(
                "/api/courses/load",
                files={
                    "file": (
                        dataset.name,
                        handle,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
        loaded.raise_for_status()
        body = loaded.json()
        assert body["success"], body
        report["loaded_count"] = body["course_count"]

        # 时间段必须完整保真（不规则周次 + 例外时段）
        slot_counts = {c["course_code"]: len(c["time_slots"]) for c in body["courses"]}
        report["courses_without_slots"] = [k for k, v in slot_counts.items() if v == 0]
        report["multi_slot_courses"] = {k: v for k, v in slot_counts.items() if v > 1}

        # 例外时段保真核对
        exception = meta.get("exception_slot")
        if exception:
            target = next(
                (c for c in body["courses"] if c["course_code"] == exception["code"]), None
            )
            assert target, f"例外时段课程 {exception['code']} 未导入"
            slots = sorted(target["time_slots"], key=lambda s: s["start_period"])
            report["exception_roundtrip"] = {
                "code": exception["code"],
                "slots": [
                    {
                        "day": s["day_of_week"],
                        "periods": f"{s['start_period']}-{s['end_period']}",
                        "weeks": s["weeks"],
                    }
                    for s in slots
                ],
                # 关键不变量：同一门课两个时段的周次必须互斥
                "weeks_disjoint": (
                    len(slots) == 2
                    and not (set(slots[0]["weeks"]) & set(slots[1]["weeks"]))
                ),
            }

        # ── 2. 全部加入已选（等价于逐门点「加入」）───────────────────
        selected = []
        for course in body["courses"]:
            response = client.post(
                "/api/selected-courses",
                data={
                    "course_code": course["course_code"],
                    "class_index": course["class_index"],
                },
            )
            response.raise_for_status()
            selected.append(response.json())
        report["selected_count"] = len(selected)

        # ── 3. 设类别（等价于课程页下拉；公共必修/二选一必须手选）────
        intended = meta["intended_categories"]
        patched = 0
        for course in selected:
            key = f"{course['course']['course_code']}#{course['class_index']}"
            want = intended.get(key)
            if want and str(course.get("custom_category", "")).strip() != want:
                response = client.patch(
                    f"/api/selected-courses/{course['id']}",
                    json={"custom_category": want},
                )
                response.raise_for_status()
                patched += 1
        report["category_patched"] = patched

        unset = [
            c["course"]["course_code"]
            for c in client.get("/api/selected-courses").json()
            if str(c.get("custom_category", "")).strip().lower() in ("", "nan")
        ]
        report["still_unset_categories"] = unset

        # ── 4. 写学分要求（等价于学分设置页）────────────────────────
        targets = {category: 0.0 for category in DEFAULT_CATEGORIES}
        targets.update(meta["targets"])
        response = client.post("/api/credits/settings", json=targets)
        response.raise_for_status()
        report["credit_targets"] = meta["targets"]

        # ── 5. 配置 + 排课 ──────────────────────────────────────────
        response = client.post(
            "/api/scheduling/config",
            json={
                "credit_constraint_mode": mode,
                "campus_conflict_mode": "PERIOD",
                "max_solutions": 1,
                "time_limit": 60,
                "credit_overflow": 1.0,
            },
        )
        response.raise_for_status()

        created = client.post("/api/scheduling/execute", json={})
        created.raise_for_status()
        task_id = created.json()["task_id"]

        import time

        deadline = time.monotonic() + 90
        final: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status = client.get(f"/api/scheduling/status/{task_id}")
            status.raise_for_status()
            final = status.json()
            if final["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.1)

        report["task_status"] = final.get("status")
        report["task_message"] = final.get("message") or final.get("error_message")

        result = final.get("result")
        if not result:
            report["result_courses"] = 0
            report["by_category"] = {}
            return report

        report["result_courses"] = len(result["selected_courses"])
        report["score"] = result["score"]

        # ── 6. 核对结果的学分归集 ───────────────────────────────────
        by_category: dict[str, dict[str, Any]] = {}
        for course in result["selected_courses"]:
            category = course["custom_category"]
            entry = by_category.setdefault(category, {"credits": 0.0, "codes": []})
            entry["credits"] = round(entry["credits"] + course["course"]["credits"], 1)
            entry["codes"].append(course["course"]["course_code"])
        report["by_category"] = by_category

        report["gap_vs_target"] = {
            category: round(target - by_category.get(category, {}).get("credits", 0.0), 1)
            for category, target in meta["targets"].items()
            if by_category.get(category, {}).get("credits", 0.0) < target
        }
        report["total_credits"] = round(
            sum(c["course"]["credits"] for c in result["selected_courses"]), 1
        )
        report["hard_conflicts"] = [
            c for c in result["conflicts"] if c["conflict_type"] in ("time", "campus")
        ]

        # 二选一：绝不该同时选两门
        pub2 = by_category.get("公共必修课 - 公共必修（二选一）", {}).get("codes", [])
        report["pub2_course_count"] = len(pub2)

        # 例外时段是否活到了结果里
        if exception:
            hit = next(
                (
                    c
                    for c in result["selected_courses"]
                    if c["course"]["course_code"] == exception["code"]
                ),
                None,
            )
            report["exception_in_result"] = (
                {
                    "slots": len(hit["time_slots"]),
                    "weeks_disjoint": len(hit["time_slots"]) == 2
                    and not (
                        set(hit["time_slots"][0]["weeks"]) & set(hit["time_slots"][1]["weeks"])
                    ),
                }
                if hit
                else None
            )

    return report


def app_client():
    """每个场景用干净的 app 状态：重置全局会话单例。"""
    import web_backend.state as state

    state._web_session_context = None
    from web_backend.server import app

    return app


def print_report(report: dict[str, Any]) -> list[str]:
    """打印并返回失败项。"""
    print(f"\n{'=' * 78}")
    print(
        f"{report['plan']} / {report['credit_mode']} / "
        f"{'跨学期供给不足' if report['scarce'] else '全年课程'}"
    )
    print("=" * 78)
    print(f"数据集 {report['dataset']}（{report['dataset_courses']} 门）")
    print(
        f"导入 {report.get('loaded_count')} → 已选 {report.get('selected_count')} "
        f"→ 手选类别 {report.get('category_patched')} 门"
    )
    print(f"任务 {report.get('task_status')}：{report.get('task_message')}")

    failures: list[str] = []

    if report.get("courses_without_slots"):
        failures.append(f"有课程丢失时间段：{report['courses_without_slots']}")
    if report.get("still_unset_categories"):
        failures.append(f"仍有课程类别未设置：{report['still_unset_categories']}")

    exc = report.get("exception_roundtrip")
    if exc:
        print(f"\n例外时段 {exc['code']}：")
        for slot in exc["slots"]:
            weeks = slot["weeks"]
            shown = f"{weeks[:3]}...{weeks[-2:]}" if len(weeks) > 5 else weeks
            print(f"   周{slot['day']} 第{slot['periods']}节  周次={shown}")
        print(f"   两段周次互斥: {exc['weeks_disjoint']}")
        if not exc["weeks_disjoint"]:
            failures.append("例外时段与常规时段周次重叠——同一周会占两个时段")

    if report.get("result_courses"):
        print(f"\n排课结果：{report['result_courses']} 门 / {report['total_credits']} 学分 "
              f"/ 评分 {report['score']['total_score']:.1f}")
        print(f"{'类别':<24} {'要求':>6} {'排入':>6} {'缺口':>6}")
        print("-" * 48)
        for category, target in report["credit_targets"].items():
            got = report["by_category"].get(category, {}).get("credits", 0.0)
            gap = report["gap_vs_target"].get(category, 0.0)
            flag = "  ←" if gap else ""
            print(f"{category:<24} {target:>6.1f} {got:>6.1f} {gap:>6.1f}{flag}")

        print(f"\n二选一选中门数: {report['exception_in_result'] and ''}{report['pub2_course_count']}")
        if report["pub2_course_count"] > 1:
            failures.append(
                f"二选一选了 {report['pub2_course_count']} 门（应最多 1 门）"
            )
        if report["hard_conflicts"]:
            failures.append(f"存在硬冲突：{report['hard_conflicts']}")

        exc_result = report.get("exception_in_result")
        if exc_result:
            print(f"例外时段在结果中: {exc_result['slots']} 段, "
                  f"周次互斥={exc_result['weeks_disjoint']}")
            if not exc_result["weeks_disjoint"]:
                failures.append("结果中的例外时段周次重叠")

        # 供给不足的类别本就该有缺口，不算失败；但供给充足却有缺口就是 bug
        for category, gap in report["gap_vs_target"].items():
            expected = report["expected_gaps"].get(category, 0.0)
            if gap > expected + 1e-6:
                failures.append(
                    f"{category} 缺口 {gap} 超出数据集预期 {expected}"
                    "（供给够却没排进去）"
                )
    else:
        print("\n无排课结果")
        if report["credit_mode"] == "OPTIMAL":
            failures.append("OPTIMAL 模式应给出部分解，却无结果")

    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", choices=("phd", "master"), default="phd")
    parser.add_argument("--scarce", action="store_true")
    parser.add_argument("--mode", choices=("OPTIMAL", "REQUIRED"), default="OPTIMAL")
    parser.add_argument("--all", action="store_true", help="跑完整矩阵")
    args = parser.parse_args()

    if args.all:
        matrix = [
            ("phd", False, "OPTIMAL"),
            ("phd", True, "OPTIMAL"),
            ("phd", True, "REQUIRED"),
            ("master", False, "OPTIMAL"),
            ("master", True, "OPTIMAL"),
        ]
    else:
        matrix = [(args.plan, args.scarce, args.mode)]

    all_failures: list[str] = []
    reports = []
    for plan, scarce, mode in matrix:
        report = run_scenario(plan, scarce, mode)
        reports.append(report)
        failures = print_report(report)
        # REQUIRED + 供给不足 → 失败是正确行为，不计入
        if mode == "REQUIRED" and scarce and report.get("task_status") == "failed":
            print("   （REQUIRED 模式在供给不足时失败 = 正确行为）")
            failures = [f for f in failures if "应给出部分解" not in f]
        all_failures.extend(f"[{report['plan']}/{mode}] {f}" for f in failures)

    out = ROOT / "test_data" / "generated" / "curriculum_e2e_report.json"
    out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 78}")
    print("VERDICT")
    print("=" * 78)
    if all_failures:
        for failure in all_failures:
            print(f"  FAIL {failure}")
        print(f"\nCURRICULUM_E2E_FAILED（{len(all_failures)} 项）")
        raise SystemExit(1)
    print(f"场景数 {len(reports)}，全部通过")
    print(f"报告 → {out.relative_to(ROOT)}")
    print("ALL_CURRICULUM_E2E_CHECKS_PASSED")


if __name__ == "__main__":
    main()
