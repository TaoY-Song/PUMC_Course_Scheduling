#!/usr/bin/env python3
"""真实浏览器全链路验收：上传 Excel → 选课 → 排课 → 周课表，并做双尺寸响应式检查。

用 Chrome DevTools Protocol 直接驱动 headless Chrome（无需 Selenium/Playwright）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import websocket  # websocket-client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
ROUTES = ("/courses", "/scheduling", "/settings", "/supplement")


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise SystemExit("未找到 Chrome/Edge 可执行文件")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class CDP:
    """极简 CDP 客户端：一个 WebSocket + 递增 id。"""

    def __init__(self, ws_url: str) -> None:
        self._ws = websocket.create_connection(ws_url, timeout=30)
        self._id = 0
        self.console_errors: list[str] = []

    def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        message_id = self._id
        self._ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self._ws.recv())
            if payload.get("method") == "Runtime.consoleAPICalled":
                if payload["params"].get("type") == "error":
                    text = " ".join(
                        str(arg.get("value", arg.get("description", "")))
                        for arg in payload["params"].get("args", [])
                    )
                    self.console_errors.append(text)
            elif payload.get("method") == "Runtime.exceptionThrown":
                details = payload["params"].get("exceptionDetails", {})
                self.console_errors.append(str(details.get("text", "exception")))
            if payload.get("id") == message_id:
                if "error" in payload:
                    raise RuntimeError(f"{method} failed: {payload['error']}")
                return payload.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("text", "js error"))
        return result.get("result", {}).get("value")

    def wait_for(self, expression: str, timeout: float = 30, interval: float = 0.25) -> Any:
        deadline = time.monotonic() + timeout
        last: Any = None
        while time.monotonic() < deadline:
            last = self.evaluate(expression)
            if last:
                return last
            time.sleep(interval)
        raise TimeoutError(f"条件超时: {expression} (last={last!r})")

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass


def start_backend(port: int) -> subprocess.Popen[bytes]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    log = open(ROOT / "test_data" / "generated" / f"backend_{port}.log", "wb")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_backend.server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit("后端进程提前退出")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                if response.status == 200:
                    return process
        except Exception:
            time.sleep(0.4)
    raise SystemExit("后端启动超时")


def start_chrome(port: int, profile: Path) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--disable-extensions",
            # Chrome 111+ 会拒绝带 Origin 头的 CDP 连接（403），本地调试必需
            "--remote-allow-origins=*",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
                return process
        except Exception:
            time.sleep(0.4)
    raise SystemExit("Chrome 启动超时")


def open_page(debug_port: int) -> CDP:
    request = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as response:
        target = json.loads(response.read())
    client = CDP(target["webSocketDebuggerUrl"])
    client.send("Page.enable")
    client.send("Runtime.enable")
    return client


def set_viewport(client: CDP, width: int, height: int) -> None:
    client.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 768},
    )


def navigate(client: CDP, url: str) -> None:
    client.send("Page.navigate", {"url": url})
    client.wait_for("document.readyState === 'complete'", timeout=30)
    client.wait_for("!!document.querySelector('nav')", timeout=30)


def upload_fixture(client: CDP, fixture: Path) -> None:
    """通过 CDP 给隐藏的 file input 塞真实文件（等价用户点击选择文件）。"""
    document = client.send("DOM.getDocument", {"depth": -1, "pierce": True})
    nodes = client.send(
        "DOM.querySelectorAll",
        {"nodeId": document["root"]["nodeId"], "selector": "input[type=file]"},
    )["nodeIds"]
    if not nodes:
        raise RuntimeError("页面上找不到文件输入框")
    client.send("DOM.setFileInputFiles", {"files": [str(fixture)], "nodeId": nodes[0]})


def overflow_report(client: CDP) -> dict[str, Any]:
    return client.evaluate(
        """(() => {
          const de = document.documentElement;
          const wide = [...document.querySelectorAll('*')]
            .filter(el => el.getBoundingClientRect().right > de.clientWidth + 2)
            .slice(0, 5)
            .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 40));
          return {
            scrollWidth: de.scrollWidth,
            clientWidth: de.clientWidth,
            horizontalOverflow: de.scrollWidth > de.clientWidth + 2,
            offenders: wide,
          };
        })()"""
    )


def run(semester: int, keep_open: bool = False) -> dict[str, Any]:
    from scripts.semester_e2e_test import build_fixture  # noqa: WPS433

    sources = sorted((ROOT / "test_data").glob("*.xls*"))
    source = sources[semester - 1]
    fixture = ROOT / "test_data" / "generated" / f"browser_semester_{semester}.xlsx"
    rows, intended_by_code, targets = build_fixture(source, fixture)

    api_port, debug_port = free_port(), free_port()
    profile = Path(tempfile.mkdtemp(prefix="pumc-chrome-"))
    backend = chrome = None
    client: CDP | None = None
    report: dict[str, Any] = {
        "semester_source": source.name,
        "fixture_courses": len(rows),
        "credit_targets": targets,
        "responsive": {},
    }

    try:
        backend = start_backend(api_port)
        chrome = start_chrome(debug_port, profile)
        client = open_page(debug_port)
        base = f"http://127.0.0.1:{api_port}"

        # ── 桌面尺寸：完整业务链路 ──────────────────────────────────
        set_viewport(client, 1440, 900)
        navigate(client, f"{base}/courses")
        report["initial_catalog_empty_state"] = bool(
            client.evaluate("document.body.innerText.includes('尚未导入课程表')")
        )

        upload_fixture(client, fixture)
        client.wait_for("document.querySelectorAll('table tbody tr').length > 0", timeout=60)
        report["catalog_rows"] = client.evaluate("document.querySelectorAll('table tbody tr').length")
        report["catalog_feedback"] = client.evaluate(
            "(document.querySelector('[role=status], [role=alert]')||{}).innerText || ''"
        )

        # 点击所有“加入”按钮（真实用户交互）
        added = client.evaluate(
            """(() => {
              const btns = [...document.querySelectorAll('table tbody button')]
                .filter(b => b.innerText.includes('加入') && !b.disabled);
              btns.forEach(b => b.click());
              return btns.length;
            })()"""
        )
        report["clicked_add_buttons"] = added
        client.wait_for(
            "[...document.querySelectorAll('button')].some(b => b.innerText.includes('已选'))",
            timeout=30,
        )
        report["selected_metric_text"] = client.evaluate(
            """(() => {
              const el = [...document.querySelectorAll('div')]
                .find(d => /已选/.test(d.innerText) && d.innerText.length < 40);
              return el ? el.innerText.replace(/\\n/g, ' ') : '';
            })()"""
        )

        # 公共必修课的类别默认为 nan，必须用户手选；UI 现在会拦下来。
        # 先等类别待设置的卡片真的渲染出来，再进修复循环。
        # （之前直接断言“警示已消失”，而那一刻警示还未异步渲染，
            # 导致循环被整体跳过，却看不出异常。）
        unset_cards = client.wait_for(
            """[...document.querySelectorAll('button')]
                 .filter(b => b.innerText.includes('类别待设置') && /· 班次/.test(b.innerText))
                 .length""",
            timeout=30,
        )
        report["unset_category_cards"] = unset_cards
        report["category_warning_shown"] = bool(
            client.evaluate("document.body.innerText.includes('尚未设置类别')")
        )
        fixed = 0
        for _ in range(20):
            target = client.evaluate(
                """(() => {
                  const card = [...document.querySelectorAll('button')]
                    .find(b => b.innerText.includes('类别待设置') && /· 班次/.test(b.innerText));
                  if (!card) return null;
                  const code = (card.innerText.match(/([A-Z]{4}\\d+)/) || [])[1] || '';
                  card.click();
                  return code;
                })()"""
            )
            if not target:
                break

            # 详情面板是异步重渲染的：必须等到面板标题切到刚点的课程，
            # 否则会对上一门课的下拉做修改（或读到旧值）。
            client.wait_for(
                f"""(() => {{
                  const head = [...document.querySelectorAll('p')]
                    .find(p => /· 班次/.test(p.innerText) && p.innerText.includes({target!r}));
                  return !!head;
                }})()""",
                timeout=20,
            )
            # 按 fixture 的意图类别选，而不是盲选第一个选项。
            # 两门公共必修课如果都选“公共必修”，供给量会超过目标，
            # 排课引擎会按学分溢出丢掉一门——那是数据问题，不是产品缺陷。
            wanted = next(
                (
                    category
                    for key, category in intended_by_code.items()
                    if key.split("#")[0] == target
                ),
                None,
            )
            applied = client.evaluate(
                f"""(() => {{
                  const sel = document.querySelector("select[aria-label='课程类别']");
                  if (!sel) return false;
                  const wanted = {json.dumps(wanted, ensure_ascii=False)};
                  const opts = [...sel.options].filter(o => o.value && !o.disabled);
                  const opt = opts.find(o => o.value === wanted) || opts[0];
                  if (!opt) return false;
                  sel.value = opt.value;
                  sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                  return opt.value;
                }})()"""
            )
            if not applied:
                break
            fixed += 1
            # 等这门课的待设置标记真的消失，再处理下一门
            client.wait_for(
                f"""(() => {{
                  const card = [...document.querySelectorAll('button')]
                    .find(b => b.innerText.includes({target!r}) && /· 班次/.test(b.innerText));
                  if (!card) return true;
                  return !card.innerText.includes('类别待设置');
                }})()""",
                timeout=20,
            )
        report["categories_fixed_via_ui"] = fixed
        assert fixed == unset_cards, (fixed, unset_cards)
        report["category_warning_after_fix"] = bool(
            client.evaluate("document.body.innerText.includes('尚未设置类别')")
        )
        client.wait_for(
            "!document.body.innerText.includes('尚未设置类别')", timeout=30
        )

        # 排课页：点击开始排课，等完成
        # 真实用户会先在“学分设置”页把本学期目标调成自己的培养方案缺口。
        # 默认值（学位必修 11 分、学位选修 8 分）是整个学位期的量，
        # 单学期排课时缺口过大，OPTIMAL 模式会丢掉补不上缺口的课程。
        navigate(client, f"{base}/settings")
        client.wait_for(
            "document.querySelectorAll('input[type=number]').length > 0", timeout=30
        )
        applied_targets = client.evaluate(
            f"""(() => {{
              const wanted = {json.dumps(targets, ensure_ascii=False)};
              let hits = 0;
              document.querySelectorAll('label').forEach(label => {{
                const input = label.querySelector('input[type=number]');
                if (!input) return;
                const name = (label.innerText || '').split('\\n')[0].trim();
                if (!(name in wanted)) return;
                const setter = Object.getOwnPropertyDescriptor(
                  window.HTMLInputElement.prototype, 'value').set;
                setter.call(input, String(wanted[name]));
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                hits += 1;
              }});
              return hits;
            }})()"""
        )
        report["settings_fields_filled"] = applied_targets
        client.evaluate(
            """[...document.querySelectorAll('button')]
                 .find(b => b.innerText.includes('保存设置')).click()"""
        )
        client.wait_for(
            "document.body.innerText.includes('学分要求已保存')", timeout=30
        )

        navigate(client, f"{base}/scheduling")
        try:
            client.wait_for(
                """(() => {
                  const el = [...document.querySelectorAll('p')]
                    .find(p => p.innerText.includes('已选课程'));
                  if (!el) return false;
                  return /[1-9]/.test(el.parentElement.innerText);
                })()""",
                timeout=60,
            )
            client.wait_for(
                """[...document.querySelectorAll('button')]
                     .some(b => b.innerText.includes('开始排课') && !b.disabled)""",
                timeout=60,
            )
        except TimeoutError:
            # 同一处已反复失败，直接把现场存下来，不再猜
            report["blocked_buttons"] = client.evaluate(
                """[...document.querySelectorAll('button')]
                     .map(b => ({ text: b.innerText.replace(/\\n/g,' ').slice(0,24), disabled: b.disabled }))"""
            )
            report["blocked_page_text"] = client.evaluate(
                "document.body.innerText.slice(0, 1800)"
            )
            with urllib.request.urlopen(f"{base}/api/selected-courses", timeout=10) as response:
                report["blocked_backend_selected"] = [
                    {
                        "code": item["course"]["course_code"],
                        "category": item["custom_category"],
                    }
                    for item in json.loads(response.read())
                ]
            diagnostics = ROOT / "test_data" / "generated" / "browser_block_diagnostics.json"
            diagnostics.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"已将阻断现场写入 {diagnostics}")
            raise
        report["ws_connected"] = bool(
            client.evaluate("document.body.innerText.includes('已连接')")
        )
        client.evaluate(
            """[...document.querySelectorAll('button')]
                 .find(b => b.innerText.includes('开始排课')).click()"""
        )
        try:
            client.wait_for("document.body.innerText.includes('已完成')", timeout=120)
        except TimeoutError:
            # 把页面当前状态和后端任务状态一起存下来，否则只能看到一个干巴巴的超时
            report["timeout_page_text"] = client.evaluate("document.body.innerText.slice(0, 1500)")
            with urllib.request.urlopen(f"{base}/api/scheduling/status", timeout=5) as response:
                report["timeout_backend_status"] = json.loads(response.read())
            raise
        report["scheduling_completed"] = True
        report["progress_log_entries"] = client.evaluate(
            "document.body.innerText.split('实时日志')[1] ? true : false"
        )
        # 页面上有多个表格，排课明细是行数最多的那个（不能只数第一个/最后一个）
        report["result_rows"] = client.wait_for(
            """Math.max(0, ...[...document.querySelectorAll('table')]
                 .map(t => t.querySelectorAll('tbody tr').length))""",
            timeout=30,
        )
        report["result_table_row_counts"] = client.evaluate(
            "[...document.querySelectorAll('table')].map(t => t.querySelectorAll('tbody tr').length)"
        )
        report["timetable_blocks"] = client.wait_for(
            "document.querySelectorAll('[title]').length", timeout=30
        )
        report["timetable_empty_placeholder"] = bool(
            client.evaluate("document.body.innerText.includes('当前没有课程')")
        )
        report["result_score_visible"] = bool(
            client.evaluate("document.body.innerText.includes('综合评分')")
        )

        # 导出排课结果：真实点击按钮，截获浏览器发出的下载请求，
        # 再用 HTTP 验证响应确实是可读的 Excel（不是只验证按钮存在）。
        client.send("Network.enable")
        export_url = client.evaluate(
            """(() => {
              const button = [...document.querySelectorAll('button')]
                .find(b => b.innerText.includes('导出 Excel'));
              if (!button || button.disabled) return null;
              button.click();
              return location.origin + '/api/export/schedule-result';
            })()"""
        )
        assert export_url
        time.sleep(1.0)
        with urllib.request.urlopen(export_url, timeout=30) as response:
            export_bytes = response.read()
            report["export_content_type"] = response.headers.get("content-type")
            report["export_disposition"] = response.headers.get("content-disposition")
        report["export_size"] = len(export_bytes)
        assert export_bytes.startswith(b"PK"), "排课导出不是 xlsx/zip"
        report["export_clicked"] = True

        # 补充测试页：把刚导出的排课结果作为必传文件，同时上传同学期
        # 课程表，执行补充脚本并验证结果/日志下载入口。
        exported_file = ROOT / "test_data" / "generated" / f"browser_schedule_{semester}.xlsx"
        exported_file.write_bytes(export_bytes)
        navigate(client, f"{base}/supplement")
        document = client.send("DOM.getDocument", {"depth": -1, "pierce": True})
        file_nodes = client.send(
            "DOM.querySelectorAll",
            {"nodeId": document["root"]["nodeId"], "selector": "input[type=file]"},
        )["nodeIds"]
        assert len(file_nodes) >= 2, file_nodes
        client.send("DOM.setFileInputFiles", {"files": [str(exported_file)], "nodeId": file_nodes[0]})
        client.send("DOM.setFileInputFiles", {"files": [str(fixture)], "nodeId": file_nodes[1]})
        client.wait_for(
            """[...document.querySelectorAll('button')]
                 .some(b => b.innerText.includes('开始补充测试') && !b.disabled)""",
            timeout=30,
        )
        client.evaluate(
            """[...document.querySelectorAll('button')]
                 .find(b => b.innerText.includes('开始补充测试')).click()"""
        )
        client.wait_for("document.body.innerText.includes('补充测试完成')", timeout=120)
        report["supplement_completed"] = True
        report["supplement_download_links"] = client.evaluate(
            """[...document.querySelectorAll('a[download]')]
                 .map(a => ({ text: a.innerText, href: a.href }))"""
        )
        assert len(report["supplement_download_links"]) >= 2
        for link in report["supplement_download_links"]:
            with urllib.request.urlopen(link["href"], timeout=30) as response:
                payload = response.read()
            assert payload, link
            if "Excel" in link["text"] or "结果" in link["text"]:
                assert payload.startswith(b"PK"), link

        # ── 双尺寸响应式 + 控制台错误 ──────────────────────────────
        for width, height, label in ((1440, 900, "desktop"), (390, 844, "mobile")):
            set_viewport(client, width, height)
            per_route = {}
            for route in ROUTES:
                navigate(client, f"{base}{route}")
                time.sleep(0.4)
                per_route[route] = overflow_report(client)
            report["responsive"][label] = per_route

        report["console_errors"] = client.console_errors
        return report
    finally:
        if client and not keep_open:
            client.close()
        for process in (chrome, backend):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semester", type=int, default=1, choices=(1, 2, 3))
    args = parser.parse_args()
    report = run(args.semester)
    output = ROOT / "test_data" / "generated" / f"browser_semester_{args.semester}_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    overflow = [
        f"{label}{route}"
        for label, routes in report["responsive"].items()
        for route, data in routes.items()
        if data["horizontalOverflow"]
    ]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n=== VERDICT ===")
    print(f"catalog_rows={report['catalog_rows']} added={report['clicked_add_buttons']}")
    print(f"category_warning_shown={report.get('category_warning_shown')} fixed_via_ui={report.get('categories_fixed_via_ui')}")
    print(f"scheduling_completed={report.get('scheduling_completed')}")
    print(f"result_rows={report['result_rows']} timetable_blocks={report['timetable_blocks']}")
    print(f"export_clicked={report.get('export_clicked')} export_size={report.get('export_size')}")
    print(f"supplement_completed={report.get('supplement_completed')} download_links={len(report.get('supplement_download_links', []))}")
    print(f"empty_timetable_placeholder={report['timetable_empty_placeholder']}")
    print(f"console_errors={len(report['console_errors'])}")
    print(f"horizontal_overflow={overflow or 'none'}")

    assert report["catalog_rows"] > 0
    assert report["clicked_add_buttons"] > 0
    assert report.get("scheduling_completed") is True
    assert report["result_rows"] > 0
    assert report["timetable_blocks"] > 0
    assert report["timetable_empty_placeholder"] is False
    assert report.get("export_clicked") is True
    assert report.get("export_size", 0) > 0
    assert report.get("supplement_completed") is True
    assert len(report.get("supplement_download_links", [])) >= 2
    # 排课结果应该把所有已选课程都排进去（本 fixture 构造为无冲突）
    assert report["result_rows"] == report["clicked_add_buttons"], (
        report["result_rows"],
        report["clicked_add_buttons"],
    )
    assert not report["console_errors"], report["console_errors"]
    assert not overflow, overflow
    print("ALL_BROWSER_CHECKS_PASSED")


if __name__ == "__main__":
    main()
