"""End-to-end API check for the async scheduling task lifecycle.

Exercises the real FastAPI app through TestClient so the DTO shapes the frontend
normalisers depend on are verified against the actual server, not a mock.
"""

import pytest
import time

pytest.importorskip("fastapi.testclient", reason="fastapi TestClient unavailable")

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from web_backend.server import app

    with TestClient(app) as test_client:
        yield test_client


def test_configure_utf8_output_handles_a_gbk_console(monkeypatch):
    import io
    import sys

    import app_web

    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)

    app_web._configure_utf8_output()
    print("✅ 启动测试")
    stream.flush()

    assert stream.encoding.lower() == "utf-8"
    assert raw.getvalue().decode("utf-8").strip() == "✅ 启动测试"


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_scheduling_config_roundtrip(client):
    """Config posted by the UI must come back unchanged."""
    payload = {
        "credit_constraint_mode": "OPTIMAL",
        "campus_conflict_mode": "PERIOD",
        "campus_equivalence_groups": [["西北旺药植所校区", "院校北区"], ["东单校区", "西院"]],
        "max_solutions": 3,
        "time_limit": 45,
        "credit_overflow": 2.0,
    }

    posted = client.post("/api/scheduling/config", json=payload)
    assert posted.status_code == 200, posted.text
    assert posted.json()["success"] is True

    fetched = client.get("/api/scheduling/config")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["max_solutions"] == 3
    assert body["time_limit"] == 45
    assert body["credit_overflow"] == pytest.approx(2.0)
    assert body["campus_conflict_mode"] == "PERIOD"
    assert body["campus_equivalence_groups"] == [
        ["西北旺药植所校区", "院校北区"],
        ["东单校区", "西院"],
    ]


def test_invalid_campus_equivalence_groups_are_rejected_without_mutating_config(client):
    valid_payload = {
        "credit_constraint_mode": "OPTIMAL",
        "campus_conflict_mode": "DAILY",
        "campus_equivalence_groups": [["西北旺药植所校区", "院校北区"]],
        "max_solutions": 1,
        "time_limit": 60,
        "credit_overflow": 1.0,
    }
    assert client.post("/api/scheduling/config", json=valid_payload).status_code == 200

    invalid_payload = {**valid_payload, "campus_equivalence_groups": [
        ["西北旺药植所校区", "院校北区"],
        ["院校北区", "东单校区"],
    ]}
    response = client.post("/api/scheduling/config", json=invalid_payload)

    assert response.status_code == 422
    assert client.get("/api/scheduling/config").json()["campus_equivalence_groups"] == [
        ["西北旺药植所校区", "院校北区"],
    ]


def test_period_mode_survives_config_roundtrip(client):
    """PERIOD 按半天时段分块判定，没有可调阈值需要回传。

    旧接口有个 campus_transition_time（“隔几节”），但那个语义
        gap = 后一门.start - 前一门.end - 1
    对 1-2→3-4（课间）与 3-4→5-6（午休）算出来都是 0，
    无法区分“赶不上”和“赶得上”，所以已删除。
    客户端就算多传该字段也不应 500。
    """
    payload = {
        "credit_constraint_mode": "OPTIMAL",
        "campus_conflict_mode": "PERIOD",
        "max_solutions": 1,
        "time_limit": 60,
        "credit_overflow": 1.0,
        "campus_transition_time": 30,  # 已废弃字段，应被忽略
    }

    response = client.post("/api/scheduling/config", json=payload)

    assert response.status_code == 200, response.text
    body = client.get("/api/scheduling/config").json()
    assert body["campus_conflict_mode"] == "PERIOD"
    assert "campus_transition_time" not in body


def test_execute_without_courses_reports_failure_not_success(client):
    """No selected courses must not yield a 'completed' task with an empty result."""
    response = client.post("/api/scheduling/execute", json={})

    assert response.status_code == 200, response.text
    body = response.json()

    # The task envelope must be present and must NOT claim completion-with-result.
    assert "task_id" in body
    assert "status" in body
    assert body["status"] != "completed"
    assert body.get("result") is None


def test_task_envelope_exposes_percent(client):
    """The frontend reads `percent`; the DTO previously never returned it."""
    response = client.post("/api/scheduling/execute", json={})

    body = response.json()
    assert "percent" in body, "task envelope is missing the percent field"
    assert isinstance(body["percent"], int)


def test_status_endpoint_keeps_task_identity(client):
    """status must return task_id/status alongside any result."""
    created = client.post("/api/scheduling/execute", json={}).json()
    task_id = created["task_id"]

    status = client.get(f"/api/scheduling/status/{task_id}")

    assert status.status_code == 200
    body = status.json()
    assert body["task_id"] == task_id
    assert "status" in body
    assert "percent" in body


def test_completed_status_includes_result_payload(client, monkeypatch):
    """Frontend polling must receive the completed result, not only has_result=true."""
    import web_backend.api.scheduling as scheduling_api
    from core.scheduling.models import ScheduleResult, ScheduleScore, ScheduleStatus
    from web_backend.services.task_runtime import SchedulingTaskRecord

    record = SchedulingTaskRecord(task_id="completed-task")
    result = ScheduleResult(
        schedule_id="schedule-1",
        selected_courses=[],
        score=ScheduleScore(total_score=88.0),
        conflicts=[],
        status=ScheduleStatus.SUCCESS,
        solve_time_seconds=0.1,
    )
    record.mark_completed(result)
    monkeypatch.setattr(scheduling_api.task_runtime, "get_task", lambda _task_id: record)

    response = client.get("/api/scheduling/status/completed-task")

    assert response.status_code == 200
    body = response.json()
    assert body["has_result"] is True
    assert body["result"] is not None
    assert body["result"]["score"]["total_score"] == pytest.approx(88.0)


def test_websocket_scheduling_event_keeps_task_id(client):
    """Real WebSocket adapter output must preserve task identity."""
    from web_backend.api.websocket import manager
    from web_backend.dependencies import get_event_manager
    from core.services.interfaces import ServiceEvent

    event_manager = get_event_manager()
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "action": "subscribe",
                "event_types": ["scheduling.progress"],
            }
        )
        assert websocket.receive_json()["type"] == "subscribed"
        event_manager.emit(
            ServiceEvent(
                event_type="scheduling_progress",
                data={"task_id": "task-current", "message": "求解中", "percent": 50},
                timestamp=time.time(),
                source="integration-test",
            )
        )
        message = websocket.receive_json()

    assert message["type"] == "scheduling.progress"
    assert message["data"]["task_id"] == "task-current"
    assert message["data"]["percent"] == 50
    assert not manager.active_connections


def test_cancel_endpoint_reports_success_for_a_pending_task_cancelled_immediately(
    client, monkeypatch
):
    import web_backend.api.scheduling as scheduling_api
    from web_backend.services.task_runtime import SchedulingTaskRecord

    record = SchedulingTaskRecord(task_id="queued-task")
    monkeypatch.setattr(scheduling_api.task_runtime, "get_task", lambda _task_id: record)

    def cancel(_task_id):
        record.mark_cancelled()
        return record

    monkeypatch.setattr(scheduling_api.task_runtime, "cancel_task", cancel)
    response = client.post("/api/scheduling/cancel/queued-task")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["status"] == "cancelled"


def test_unknown_task_returns_404(client):
    response = client.get("/api/scheduling/status/does-not-exist")
    assert response.status_code == 404


def test_artifact_download_rejects_windows_path_traversal(client, tmp_path):
    """Windows 反斜杠是分隔符；`..%5Cfile` 不能逃出 artifacts_dir。"""
    from web_backend.state import get_web_session_context

    web_session = get_web_session_context()
    web_session.artifacts_dir = tmp_path / "exports"
    web_session.artifacts_dir.mkdir()
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("SECRET", encoding="utf-8")

    response = client.get("/api/export/download/..%5Coutside-secret.txt")

    assert response.status_code == 400
    assert "SECRET" not in response.text


def test_artifact_download_accepts_generated_file(client, tmp_path):
    from web_backend.state import get_web_session_context

    web_session = get_web_session_context()
    web_session.artifacts_dir = tmp_path / "exports"
    web_session.artifacts_dir.mkdir()
    artifact = web_session.artifacts_dir / "result.log"
    artifact.write_text("OK", encoding="utf-8")

    response = client.get("/api/export/download/result.log")

    assert response.status_code == 200
    assert response.text == "OK"


def test_course_upload_rejects_files_above_configured_limit(client, monkeypatch):
    from web_backend.uploads import settings as upload_settings

    monkeypatch.setattr(upload_settings, "max_upload_size", 16)
    response = client.post(
        "/api/courses/load",
        files={"file": ("too-large.xlsx", b"x" * 17, "application/vnd.ms-excel")},
    )

    assert response.status_code == 413


def test_selected_course_import_rejects_files_above_configured_limit(client, monkeypatch):
    from web_backend.uploads import settings as upload_settings

    monkeypatch.setattr(upload_settings, "max_upload_size", 16)
    response = client.post(
        "/api/import/selected-courses",
        files={"file": ("too-large.xlsx", b"x" * 17, "application/vnd.ms-excel")},
    )

    assert response.status_code == 413


def test_supplement_rejects_files_above_configured_limit(client, monkeypatch):
    from web_backend.uploads import settings as upload_settings

    monkeypatch.setattr(upload_settings, "max_upload_size", 16)
    response = client.post(
        "/api/supplement/run",
        files={"schedule_result_file": ("too-large.xlsx", b"x" * 17, "application/vnd.ms-excel")},
    )

    assert response.status_code == 413


def test_failed_course_upload_preserves_the_previous_catalog(client, tmp_path):
    from core.models import Course
    from web_backend.state import get_web_session_context

    session = get_web_session_context()
    session.artifacts_dir = tmp_path / "exports"
    session.artifacts_dir.mkdir()
    old_path = session.artifacts_dir / "current_course_catalog.xlsx"
    old_path.write_bytes(b"previous valid workbook")
    previous = Course("OLD-1", "原课程", "d", "选修", 1, "东单", "t", 1.0, 16)
    session.set_loaded_courses([previous], str(old_path), reset_selection=False)

    response = client.post(
        "/api/courses/load",
        files={"file": ("broken.xlsx", b"not really an excel file", "application/vnd.ms-excel")},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert [course.code for course in session.loaded_courses] == ["OLD-1"]
    assert session.loaded_course_file == str(old_path)
    assert old_path.read_bytes() == b"previous valid workbook"
    assert not list(session.artifacts_dir.glob("course_catalog_pending.*"))


def test_course_load_rejects_non_excel_extension(client):
    response = client.post(
        "/api/courses/load",
        files={"file": ("courses.txt", b"not excel", "text/plain")},
    )

    assert response.status_code == 400


def test_failed_selected_course_import_preserves_existing_selection(
    client, monkeypatch, tmp_path
):
    from core.models import Course, SelectedCourse
    from web_backend.state import get_web_session_context

    session = get_web_session_context()
    course = Course("KEEP-1", "保留课程", "d", "选修", 1, "东单", "t", 1.0, 16)
    selected = SelectedCourse(course, 1, [], False, "选修课 - 学位选修")
    session.loaded_courses = [course]
    session.selected_courses = {"keep-id": selected}

    monkeypatch.setattr(session.data_service, "import_selected_courses", lambda *_args: [])
    response = client.post(
        "/api/import/selected-courses",
        files={"file": ("empty.xlsx", b"small", "application/vnd.ms-excel")},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert session.selected_courses == {"keep-id": selected}
    assert not list(tmp_path.glob("*.xlsx"))


def test_excel_only_upload_endpoints_reject_non_excel_files(client):
    selected_response = client.post(
        "/api/import/selected-courses",
        files={"file": ("selected.txt", b"not excel", "text/plain")},
    )
    supplement_response = client.post(
        "/api/supplement/run",
        files={"schedule_result_file": ("schedule.txt", b"not excel", "text/plain")},
    )

    assert selected_response.status_code == 400
    assert supplement_response.status_code == 400


def test_course_load_failure_reports_success_false(client):
    """A bad upload returns HTTP 200 + success:false, which the client must detect."""
    response = client.post(
        "/api/courses/load",
        files={"file": ("broken.xlsx", b"not really an excel file", "application/vnd.ms-excel")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["course_count"] == 0
