#!/usr/bin/env python3
"""检查关键交互元素的前景/背景对比度，防止“白字白底”类隐形 bug 复发。

背景：已选课程卡片的 active 态曾把 ``color: white`` 配上一个不存在的
CSS 变量（``--sidebar-bg``），变量静默解析为空 → 背景仍是白色 →
标题、编码、移除按钮全部隐形。构建、类型检查、E2E 断言都不会失败，
因为 DOM 里文字确实存在，只是看不见。

这里直接读浏览器算出的 computed style，按 WCAG 相对亮度算对比度，
低于阈值即失败。用法：

    python scripts/verify_contrast.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_e2e_test import (  # noqa: E402
    CDP,
    free_port,
    open_page,
    navigate,
    set_viewport,
    start_backend,
    start_chrome,
    upload_fixture,
)

# WCAG 对比度阈值。正文用 4.5，这里放宽到 3.0：
# 只拦“基本看不见”的情况，不做完整无障碍评级。
MIN_CONTRAST = 3.0

CONTRAST_PROBE = r"""
(() => {
  function parseColor(value) {
    const m = String(value).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(s => parseFloat(s.trim()));
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  }
  function channel(c) {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  }
  function luminance(c) {
    return 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);
  }
  // 元素自身背景可能透明，需向上找第一个不透明祖先。
  function effectiveBackground(el) {
    let node = el;
    while (node && node !== document.documentElement) {
      const bg = parseColor(getComputedStyle(node).backgroundColor);
      if (bg && bg.a > 0.1) return bg;
      node = node.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  }
  function contrast(el) {
    const fg = parseColor(getComputedStyle(el).color);
    if (!fg) return null;
    const bg = effectiveBackground(el);
    const l1 = luminance(fg), l2 = luminance(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    return {
      text: (el.innerText || '').trim().slice(0, 30),
      color: getComputedStyle(el).color,
      background: `rgb(${Math.round(bg.r)}, ${Math.round(bg.g)}, ${Math.round(bg.b)})`,
      ratio: Math.round(ratio * 100) / 100,
    };
  }

  const results = [];
  // 已选课程卡片。active 态由 accent 色边框标识，位置不固定，
  // 因此按边框色判定，而不是假设第一张就是选中的那张。
  const cards = [...document.querySelectorAll('button')].filter(
    b => /· 班次/.test(b.innerText) && !b.innerText.includes('加入')
  );
  cards.slice(0, 3).forEach((card) => {
    const border = getComputedStyle(card).borderTopColor;
    const bg = parseColor(getComputedStyle(card).backgroundColor);
    // accent-ui #0d9488 -> rgb(13, 148, 136)
    const isActive = /13,\s*148,\s*136/.test(border);
    const label = isActive ? 'ACTIVE' : 'idle';
    const title = card.querySelector('p');
    if (title) {
      const c = contrast(title);
      if (c) results.push({ where: `selected-card (${label}) title`, ...c });
    }
    const remove = [...card.querySelectorAll('button')].find(b => b.innerText.includes('移除'));
    if (remove) {
      const c = contrast(remove);
      if (c) results.push({ where: `selected-card (${label}) remove-button`, ...c });
    }
    void bg;
  });

  // 搜索框：输入文字是 text-white，背景应为深色
  const search = document.querySelector('input[aria-label="搜索课程"]');
  if (search) {
    const c = contrast(search);
    if (c) results.push({ where: 'catalog search input', ...c, text: '(input)' });
  }
  return results;
})()
"""


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    fixture = root / "test_data" / "generated" / "browser_semester_1.xlsx"
    if not fixture.exists():
        print(f"缺少 fixture：{fixture}\n请先运行：python scripts/browser_e2e_test.py --semester 1")
        return 2

    backend_port = free_port()
    debug_port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="pumc-contrast-"))
    backend = chrome = None
    client: CDP | None = None

    try:
        backend = start_backend(backend_port)
        chrome = start_chrome(debug_port, profile)
        client = open_page(debug_port)
        set_viewport(client, 1440, 900)

        base = f"http://127.0.0.1:{backend_port}"
        navigate(client, f"{base}/courses")
        upload_fixture(client, fixture)
        client.wait_for("document.querySelectorAll('table tbody tr').length > 0", timeout=60)

        # 加入 2 门课，才能同时看到 active 与非 active 卡片
        client.evaluate(
            """(() => {
              const buttons = [...document.querySelectorAll('button')]
                .filter(b => b.innerText.includes('加入') && !b.disabled);
              buttons.slice(0, 2).forEach(b => b.click());
            })()"""
        )
        client.wait_for(
            """[...document.querySelectorAll('button')]
                 .filter(b => /· 班次/.test(b.innerText) && !b.innerText.includes('加入')).length >= 2""",
            timeout=30,
        )
        time.sleep(0.4)  # 等 React 提交样式

        results: list[dict[str, Any]] = client.evaluate(CONTRAST_PROBE)
        print(json.dumps(results, ensure_ascii=False, indent=2))

        failures = [r for r in results if r["ratio"] < MIN_CONTRAST]
        console_errors = client.console_errors

        print("\n=== VERDICT ===")
        for r in results:
            flag = "FAIL" if r["ratio"] < MIN_CONTRAST else "ok  "
            print(f"{flag} {r['ratio']:>6}:1  {r['where']}  fg={r['color']} bg={r['background']}")
        print(f"console_errors={len(console_errors)}")

        if failures:
            print(f"\nCONTRAST_CHECK_FAILED: {len(failures)} 处对比度低于 {MIN_CONTRAST}:1（文字接近隐形）")
            return 1
        if console_errors:
            print(f"\nCONSOLE_ERRORS: {console_errors[:3]}")
            return 1
        print("\nALL_CONTRAST_CHECKS_PASSED")
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
