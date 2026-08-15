#!/usr/bin/env python3
"""验证课程搜索框的可见性、模糊匹配与预览下拉。

针对三个具体缺陷：
1. 输入光标不可见（caret 与文字同为白色，画在白底上）
2. 搜索只做 includes()，漏字搜不到、命中不排序、无高亮
3. 无实时预览，必须盯着下方表格自己找

用法：python scripts/verify_search_ui.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_e2e_test import (  # noqa: E402
    CDP,
    free_port,
    navigate,
    open_page,
    set_viewport,
    start_backend,
    start_chrome,
    upload_fixture,
)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    fixture = root / "test_data" / "generated" / "browser_semester_1.xlsx"
    if not fixture.exists():
        print(f"缺少 fixture：{fixture}\n请先运行：python scripts/browser_e2e_test.py --semester 1")
        return 2

    backend_port = free_port()
    debug_port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="pumc-search-"))
    backend = chrome = None
    client: CDP | None = None
    report: dict = {}

    try:
        backend = start_backend(backend_port)
        chrome = start_chrome(debug_port, profile)
        client = open_page(debug_port)
        set_viewport(client, 1440, 900)

        base = f"http://127.0.0.1:{backend_port}"
        navigate(client, f"{base}/courses")
        upload_fixture(client, fixture)
        client.wait_for("document.querySelectorAll('table tbody tr').length > 0", timeout=60)
        total_rows = client.evaluate("document.querySelectorAll('table tbody tr').length")
        report["catalog_rows"] = total_rows

        # ── 1. caret 可见性：caret-color 必须与背景有对比 ──────────────
        caret = client.evaluate(
            """(() => {
              const input = document.querySelector('input[aria-label="搜索课程"]');
              if (!input) return null;
              const cs = getComputedStyle(input);
              // 向上找不透明背景
              let node = input, bg = 'rgba(0, 0, 0, 0)';
              while (node && node !== document.documentElement) {
                const c = getComputedStyle(node).backgroundColor;
                const m = c.match(/rgba?\\(([^)]+)\\)/);
                if (m) {
                  const p = m[1].split(',').map(Number);
                  if (p.length < 4 || p[3] > 0.1) { bg = c; break; }
                }
                node = node.parentElement;
              }
              return { caretColor: cs.caretColor, color: cs.color, background: bg };
            })()"""
        )
        report["caret"] = caret
        assert caret, "找不到搜索输入框"
        # caret 与背景不能是同一个颜色
        caret_visible = caret["caretColor"] != caret["background"] and caret["color"] != caret["background"]
        report["caret_visible"] = caret_visible

        # ── 2. 真实键入后光标与文字可见，且预览下拉出现 ────────────────
        client.evaluate("document.querySelector('input[aria-label=\"搜索课程\"]').focus()")
        for char in "生物":
            client.send(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "text": char, "unmodifiedText": char},
            )
            client.send("Input.dispatchKeyEvent", {"type": "keyUp", "text": char})
            time.sleep(0.12)
        time.sleep(0.4)

        report["input_value"] = client.evaluate(
            "document.querySelector('input[aria-label=\"搜索课程\"]').value"
        )
        report["preview_open"] = client.evaluate(
            "!!document.querySelector('#course-search-preview')"
        )
        report["preview_items"] = client.evaluate(
            "document.querySelectorAll('#course-search-preview [role=option]').length"
        )
        report["highlight_marks"] = client.evaluate(
            "document.querySelectorAll('#course-search-preview mark').length"
        )
        report["highlighted_text"] = client.evaluate(
            """[...document.querySelectorAll('#course-search-preview mark')]
                 .map(m => m.textContent).slice(0, 5)"""
        )
        report["filtered_rows"] = client.evaluate(
            "document.querySelectorAll('table tbody tr').length"
        )

        # ── 3. 子序列匹配：漏字也能搜到（原 includes 做不到）──────────
        #    查询串从 fixture 里真实课名派生：取首尾各一字、跳过中间，
        #    这样断言不依赖某个特定学期恰好有哪门课。
        probe = client.evaluate(
            """(() => {
              const row = document.querySelector('table tbody tr');
              if (!row) return null;
              const name = row.querySelector('p').innerText.trim();
              if (name.length < 4) return null;
              // 取第 1、2 和最后一个字，中间留空 → 只有子序列匹配能命中
              return { name, query: name[0] + name[1] + name[name.length - 1] };
            })()"""
        )
        report["subsequence_probe"] = probe
        assert probe, "表格中没有可用于派生子序列查询的课程名"

        client.evaluate(
            f"""(() => {{
              const input = document.querySelector('input[aria-label="搜索课程"]');
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              setter.call(input, {json.dumps(probe["query"])});
              input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }})()"""
        )
        time.sleep(0.5)
        report["subsequence_rows"] = client.evaluate(
            "document.querySelectorAll('table tbody tr').length"
        )
        report["subsequence_first"] = client.evaluate(
            """(() => {
              const row = document.querySelector('table tbody tr');
              return row ? row.querySelector('p').innerText.trim() : null;
            })()"""
        )

        # ── 4. 多关键词 AND ─────────────────────────────────────────
        client.evaluate(
            """(() => {
              const input = document.querySelector('input[aria-label="搜索课程"]');
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              setter.call(input, '不存在关键词 生物');
              input.dispatchEvent(new Event('input', { bubbles: true }));
            })()"""
        )
        time.sleep(0.5)
        report["and_semantics_rows"] = client.evaluate(
            "document.querySelectorAll('table tbody tr').length"
        )

        # ── 5. 清除按钮恢复全量 ────────────────────────────────────
        client.evaluate(
            """(() => {
              const btn = document.querySelector('button[aria-label="清除搜索"]');
              if (btn) btn.click();
            })()"""
        )
        time.sleep(0.4)
        report["rows_after_clear"] = client.evaluate(
            "document.querySelectorAll('table tbody tr').length"
        )

        report["console_errors"] = client.console_errors

        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("\n=== VERDICT ===")
        print(f"caret_visible={report['caret_visible']} (caret={caret['caretColor']} bg={caret['background']})")
        print(f"input_value={report['input_value']!r}")
        print(f"preview_open={report['preview_open']} items={report['preview_items']} marks={report['highlight_marks']}")
        print(f"highlighted={report['highlighted_text']}")
        print(f"filtered_rows={report['filtered_rows']} / {total_rows}")
        probe_query = (report.get("subsequence_probe") or {}).get("query", "?")
        probe_name = (report.get("subsequence_probe") or {}).get("name", "?")
        print(f"subsequence({probe_query!r} ← {probe_name!r}) rows={report['subsequence_rows']} first={report['subsequence_first']!r}")
        print(f"AND('不存在关键词 生物') rows={report['and_semantics_rows']}")
        print(f"rows_after_clear={report['rows_after_clear']}")
        print(f"console_errors={len(report['console_errors'])}")

        failures = []
        if not report["caret_visible"]:
            failures.append("光标/文字与背景同色，输入不可见")
        if report["input_value"] != "生物":
            failures.append(f"键入未生效：{report['input_value']!r}")
        if not report["preview_open"]:
            failures.append("预览下拉未出现")
        if report["preview_items"] == 0:
            failures.append("预览下拉无候选项")
        if report["highlight_marks"] == 0:
            failures.append("预览未高亮命中片段")
        if report["filtered_rows"] >= total_rows:
            failures.append("搜索未过滤表格")
        if report["subsequence_rows"] == 0:
            failures.append(
                f"子序列匹配失效：{probe_query!r} 应命中 {probe_name!r}"
            )
        if report["and_semantics_rows"] != 0:
            failures.append("多关键词未按 AND 处理")
        if report["rows_after_clear"] != total_rows:
            failures.append("清除搜索未恢复全量")
        if report["console_errors"]:
            failures.append(f"控制台报错：{report['console_errors'][:2]}")

        if failures:
            print("\nSEARCH_UI_CHECKS_FAILED:")
            for item in failures:
                print(f"  - {item}")
            return 1
        print("\nALL_SEARCH_UI_CHECKS_PASSED")
        return 0
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        for process in (chrome, backend):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except Exception:
                    process.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
