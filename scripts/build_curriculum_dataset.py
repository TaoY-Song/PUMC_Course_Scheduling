#!/usr/bin/env python3
"""构造贴合真实培养方案的测试数据集。

之前的 fixture 是「6 门课刚好凑满、每次 96.4 分」的理想化数据，验证不了
真实场景。这里按用户提供的两套培养方案构造，并刻意编入三类真实特征：

1. **跨学期供给不足**：课程分春/秋学期开，单学期拿不到全部学分。
   核心课要 11 分但本学期只开 6 分，是最常见的情况。
2. **不规则周次**：不是清一色 1-20 周。真实的是 2-18、3-5、
   1-8+10+12-13 这种，也包括「第2-18周」这类带包裹的写法。
3. **例外时段**：一门课常规在周四上午，但第 15、17 周改到晚上。
   同一门课的两个 TimeSlot 周次互斥，冲突检测按周次区分。

用法：
    python scripts/build_curriculum_dataset.py --plan phd
    python scripts/build_curriculum_dataset.py --plan master --scarce
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

PUB = "公共必修课 - 公共必修"
PUB2 = "公共必修课 - 公共必修（二选一）"
CORE = "学位必修课（核心课）"
LIM = "选修课 - 限制性选修"
GEN = "选修课 - 通识选修"
DEG = "选修课 - 学位选修"

#: 规范类别 → 一览表里的源标签（loader 靠它自动归类）
SOURCE_LABEL = {
    PUB: "公共必修课",
    PUB2: "公共必修课",
    CORE: "学位必修课",
    LIM: "限制选修课",
    GEN: "通识选修课",
    DEG: "学位选修课",
}

#: 培养方案学分要求。课程学分 + 必修环节 7 分 = 方案总要求。
#: 必修环节（开题、文献综述等）不是课，系统里由用户填为已修学分。
PLANS = {
    "phd": {
        "label": "博士（药理学）",
        "total": 33.0,
        "non_course_credits": 7.0,
        "targets": {PUB: 4.0, PUB2: 1.0, CORE: 11.0, LIM: 1.0, GEN: 1.0, DEG: 8.0},
    },
    "master": {
        "label": "硕士（药理学）",
        "total": 32.0,
        "non_course_credits": 7.0,
        "targets": {PUB: 5.0, PUB2: 1.0, CORE: 8.0, LIM: 1.0, GEN: 1.0, DEG: 9.0},
    },
}

#: 真实课程（编码/课名/学分取自用户提供的培养方案与一览表）。
#: semester 标注该课在哪个学期开——用于模拟跨学期供给不足。
COURSES: list[dict[str, Any]] = [
    # ── 公共必修：两门都必须上 ────────────────────────────────────────
    {"code": "PUBL38001", "name": "中国马克思主义与当代", "credits": 2.0, "hours": 36.0,
     "category": PUB, "dept": "马克思主义学院", "semester": "both"},
    {"code": "PUBL38009", "name": "博士高级学术英语", "credits": 2.0, "hours": 48.0,
     "category": PUB, "dept": "外语系", "semester": "both", "plans": ["phd"]},
    {"code": "PUBL38003", "name": "研究生综合学术英语", "credits": 3.0, "hours": 54.0,
     "category": PUB, "dept": "外语系", "semester": "both", "plans": ["master"]},
    # ── 公共必修（二选一）：开两门，只该选一门 ──────────────────────
    {"code": "PUBL38004", "name": "自然辩证法概论", "credits": 1.0, "hours": 20.0,
     "category": PUB2, "dept": "马克思主义学院", "semester": "both"},
    {"code": "PUBL38005", "name": "马克思恩格斯列宁经典著作选读", "credits": 1.0, "hours": 20.0,
     "category": PUB2, "dept": "马克思主义学院", "semester": "both"},
    # ── 学位必修（核心课）：药理学，春秋分开 ────────────────────────
    {"code": "PHAR08001", "name": "新药药理学", "credits": 3.0, "hours": 59.0,
     "category": CORE, "dept": "药物研究所", "semester": "autumn"},
    {"code": "PHAR08003", "name": "分子药理学", "credits": 3.0, "hours": 74.0,
     "category": CORE, "dept": "药物研究所", "semester": "autumn"},
    {"code": "PHAR08035", "name": "药物代谢及药代动力学", "credits": 3.0, "hours": 55.0,
     "category": CORE, "dept": "药物研究所", "semester": "autumn"},
    {"code": "PHAR08012", "name": "实验药理学", "credits": 2.5, "hours": 46.0,
     "category": CORE, "dept": "药物研究所", "semester": "autumn"},
    {"code": "PHAR08039", "name": "药物毒理学研究进展", "credits": 2.0, "hours": 39.0,
     "category": CORE, "dept": "药物研究所", "semester": "spring"},
    {"code": "PHAR08014", "name": "药理学研究进展讲座", "credits": 2.0, "hours": 45.0,
     "category": CORE, "dept": "药物研究所", "semester": "spring"},
    # ── 限制性选修 ───────────────────────────────────────────────────
    {"code": "PHAR08062", "name": "药事管理法规和药品注册管理", "credits": 1.5, "hours": 30.0,
     "category": LIM, "dept": "药物研究所", "semester": "autumn"},
    # ── 通识选修：固定池子里随便选一门 ──────────────────────────────
    {"code": "CULT05003", "name": "世界医学荟萃", "credits": 1.0, "hours": 20.0,
     "category": GEN, "dept": "人文学院", "semester": "both"},
    {"code": "CULT38010", "name": "心理健康与沟通艺术", "credits": 1.0, "hours": 20.0,
     "category": GEN, "dept": "人文学院", "semester": "autumn"},
    # ── 学位选修 ─────────────────────────────────────────────────────
    {"code": "PHAR08026", "name": "药物信息学", "credits": 2.0, "hours": 49.0,
     "category": DEG, "dept": "药物研究所", "semester": "autumn"},
    {"code": "PHAR08059", "name": "实验病理学技术", "credits": 2.5, "hours": 51.0,
     "category": DEG, "dept": "药物研究所", "semester": "spring"},
    {"code": "PHAR08080", "name": "药理学研究新技术与新方法", "credits": 3.0, "hours": 60.0,
     "category": DEG, "dept": "药物研究所", "semester": "spring"},
    {"code": "PHAR09003", "name": "中药药理学专论", "credits": 3.0, "hours": 63.0,
     "category": DEG, "dept": "药物研究所", "semester": "spring"},
    {"code": "BIOL05035", "name": "英文科技论文写作", "credits": 1.5, "hours": 30.0,
     "category": DEG, "dept": "生物系", "semester": "autumn"},
]

#: 真实的不规则周次写法（第一层：学期前半）。轮着用，覆盖各种解析分支。
#: 全部限在 1-9 周内，确保与第二层（后半学期）严格不相交。
#: 之前第一层用 1-16 / 2-18、第二层用 11-18，两层在 11-16 周重叠，
#: 同时段的两门课真冲突，导致数据集自己造出一堆“排不进去”。
WEEK_PATTERNS = [
    "1-8",
    "2-9",
    "第1-8周",          # 带包裹，曾解析为空
    "1-6,8",           # 断续
    "3-9",
    "第2-9周",
]

#: 第二层：学期后半，与第一层（1-9 周）无交集。
LATE_WEEK_PATTERNS = [
    "11-18",
    "第12-19周",
    "13-20",
    "10-17",
]

#: 校区按天固定（同一天同校区，避免构造出必然冲突的数据）
DAY_CAMPUS = {1: "东单校区", 2: "东单校区", 3: "北礼士路校区", 4: "东单校区", 5: "院校北区"}
#: 三个半天时段的起始节次：上午 1-4 / 下午 5-8 / 晚上 9-10
BLOCKS = [(1, 4), (5, 8), (9, 10)]


def _slot_pool() -> list[tuple[int, int, int]]:
    """(weekday, start, end) 的确定性池子：5 天 × 3 时段 = 15 格。

    真实课表里周次不相交的课可以共用时段，所以调用方会给同一格
    分配“前半学期 / 后半学期”两层——容量实际是 30 门。
    """
    pool = []
    for start, end in BLOCKS:
        for day in sorted(DAY_CAMPUS):
            pool.append((day, start, end))
    return pool


def build(plan_key: str, *, scarce: bool, with_exception: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    plan = PLANS[plan_key]

    # scarce 模式模拟「只看本学期」：春季课全部拿不到
    def available(course: dict[str, Any]) -> bool:
        if course.get("plans") and plan_key not in course["plans"]:
            return False
        if scarce and course["semester"] == "spring":
            return False
        return True

    picked = [c for c in COURSES if available(c)]
    pool = _slot_pool()
    if len(picked) > len(pool) * 2:
        raise SystemExit(
            f"课程数 {len(picked)} 超出时段池容量 {len(pool) * 2}，"
            "请扩充 BLOCKS 或减少课程"
        )

    rows: list[dict[str, Any]] = []
    intended: dict[str, str] = {}
    supplied: dict[str, float] = {}
    exception_note: dict[str, Any] | None = None

    for index, course in enumerate(picked):
        # 超过时段池后转入第二层：同一时段、后半学期周次，与第一层不相交。
        # 之前超出直接 break，导致尾部类别（学位选修）抽不到课，
        # 报出来的“缺口”是时段池截断造成的假缺口，不是培养方案的真缺口。
        layer, slot_index = divmod(index, len(pool))
        day, start, end = pool[slot_index]
        if layer == 0:
            weeks = WEEK_PATTERNS[index % len(WEEK_PATTERNS)]
        else:
            weeks = LATE_WEEK_PATTERNS[index % len(LATE_WEEK_PATTERNS)]

        row = {
            "课程编码": course["code"],
            "课程名称": course["name"],
            "开课院系": course["dept"],
            "课程类别": SOURCE_LABEL[course["category"]],
            "班次": 1,
            "校区": DAY_CAMPUS[day],
            "任课教师": "待定",
            "学分": course["credits"],
            "学时": course["hours"],
            "选课说明": f"{plan['label']} 培养方案测试数据",
            "星期": day,
            "开始节次": start,
            "结束节次": end,
            "周次": weeks,
        }

        # 例外时段：给第一门核心课加「某几周换时段」
        # 常规周四上午 → 第 6、8 周改到晚上 9-10 节。
        # 关键：常规段必须扣掉这几周。不扣就是同一周占两个时段，
        # 正是 UI 里“例外周自动扣周”要防的那个手工遗漏。
        # 例外周也限在第一层范围（1-9）内，不踩到第二层。
        if with_exception and exception_note is None and course["category"] == CORE:
            exception_weeks = [6, 8]
            regular_weeks = [w for w in range(1, 10) if w not in exception_weeks]
            row["周次"] = ",".join(str(w) for w in regular_weeks)
            row["星期2"] = day
            row["开始节次2"] = 9
            row["结束节次2"] = 10
            row["周次2"] = ",".join(str(w) for w in exception_weeks)
            exception_note = {
                "code": course["code"],
                "name": course["name"],
                "regular": f"周{day} 第{start}-{end}节 第1-9周（扣除 6、8）",
                "exception": f"周{day} 第9-10节 第6,8周",
                "regular_weeks": regular_weeks,
                "exception_weeks": exception_weeks,
            }

        rows.append(row)
        intended[f"{course['code']}#1"] = course["category"]
        supplied[course["category"]] = supplied.get(course["category"], 0.0) + course["credits"]

    frame = pd.DataFrame(rows)
    targets = plan["targets"]
    meta = {
        "plan": plan_key,
        "plan_label": plan["label"],
        "plan_total_credits": plan["total"],
        "non_course_credits": plan["non_course_credits"],
        "scarce_semester": scarce,
        "with_exception_slot": with_exception,
        "course_count": len(rows),
        "targets": targets,
        "supplied": {k: round(v, 1) for k, v in supplied.items()},
        # 本学期拿不到的缺口——这才是真实情况，不是 bug
        "expected_gaps": {
            category: round(target - supplied.get(category, 0.0), 1)
            for category, target in targets.items()
            if supplied.get(category, 0.0) < target
        },
        "intended_categories": intended,
        "exception_slot": exception_note,
        "week_patterns_used": sorted({row["周次"] for row in rows}),
    }
    return frame, meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", choices=sorted(PLANS), default="phd")
    parser.add_argument("--scarce", action="store_true", help="只保留本学期开的课（模拟跨学期供给不足）")
    parser.add_argument("--no-exception", action="store_true", help="不构造例外时段")
    args = parser.parse_args()

    frame, meta = build(args.plan, scarce=args.scarce, with_exception=not args.no_exception)

    suffix = f"{args.plan}{'_scarce' if args.scarce else ''}"
    out_dir = ROOT / "test_data" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx = out_dir / f"curriculum_{suffix}.xlsx"
    meta_path = out_dir / f"curriculum_{suffix}_meta.json"
    frame.to_excel(xlsx, index=False)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== {meta['plan_label']} ===")
    print(f"方案总要求 {meta['plan_total_credits']} 分"
          f"（含必修环节 {meta['non_course_credits']} 分，非课程）")
    print(f"跨学期模式: {'是（春季课不可选）' if meta['scarce_semester'] else '否（全年课程）'}")
    print(f"课程数: {meta['course_count']}")
    print()
    print(f"{'类别':<24} {'要求':>6} {'本学期可选':>10} {'缺口':>6}")
    print("-" * 52)
    for category, target in meta["targets"].items():
        got = meta["supplied"].get(category, 0.0)
        gap = meta["expected_gaps"].get(category, 0.0)
        flag = "  ←" if gap else ""
        print(f"{category:<24} {target:>6.1f} {got:>10.1f} {gap:>6.1f}{flag}")
    print()
    print(f"周次写法: {', '.join(meta['week_patterns_used'])}")
    if meta["exception_slot"]:
        exc = meta["exception_slot"]
        print(f"例外时段: {exc['name']}（{exc['code']}）")
        print(f"   常规 {exc['regular']}")
        print(f"   例外 {exc['exception']}")
    print()
    print(f"→ {xlsx.relative_to(ROOT)}")
    print(f"→ {meta_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
