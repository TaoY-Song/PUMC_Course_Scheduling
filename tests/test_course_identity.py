"""课程编码作为身份键的回归覆盖。

课程编码缺失时整列曾被填成同一个常量 "UNKNOWN"，导致：
  * 前端 (course_code, class_index) 去重键全表相同 —— 加一门课，整张表变灰；
  * 后端按编码查课命中多条后静默取第一条 —— 点 A 加进去的是 B。
"""

import pandas as pd
import pytest

from core.data_loader import AUTO_CODE_PREFIX, CourseDataLoader

BASE_ROWS = {
    "课程名称": ["医学统计学", "分子生物学", "科研伦理"],
    "开课院系": ["基础学院"] * 3,
    "课程类别": ["公共必修课", "核心课", "学位选修课"],
    "班次": [1, 1, 1],
    "校区": ["校本部"] * 3,
    "任课教师": ["张三", "李四", "王五"],
    "学分": [2.0, 3.0, 1.0],
    "学时": [36, 54, 18],
}


def write_catalog(tmp_path, **columns) -> str:
    path = tmp_path / "catalog.xlsx"
    pd.DataFrame({**BASE_ROWS, **columns}).to_excel(path, index=False)
    return str(path)


def load(path) -> CourseDataLoader:
    loader = CourseDataLoader()
    assert loader.load_from_excel(path) is True
    return loader


def identity_keys(loader: CourseDataLoader):
    return [(course.code, course.class_num) for course in loader.get_courses()]


def test_course_code_alias_is_recognised(tmp_path):
    """学校发的表常把表头写成『课程编号』。"""
    loader = load(write_catalog(tmp_path, 课程编号=["G0001", "G0002", "G0003"]))

    assert [code for code, _ in identity_keys(loader)] == ["G0001", "G0002", "G0003"]
    assert any("课程编号" in warning for warning in loader.column_warnings)


@pytest.mark.parametrize("alias", ["课程编号", "课程代码", "课程号", "课程代号"])
def test_every_supported_alias_maps_to_the_canonical_column(tmp_path, alias):
    loader = load(write_catalog(tmp_path, **{alias: ["G0001", "G0002", "G0003"]}))

    assert [code for code, _ in identity_keys(loader)] == ["G0001", "G0002", "G0003"]


def test_missing_code_column_still_yields_unique_keys(tmp_path):
    """核心回归：缺列不能让所有课程共用一个键。"""
    loader = load(write_catalog(tmp_path))

    keys = identity_keys(loader)
    assert len(set(keys)) == len(keys) == 3
    assert all(code.startswith(AUTO_CODE_PREFIX) for code, _ in keys)


def test_blank_code_cells_do_not_collapse_into_one_key(tmp_path):
    """astype(str) 会把 NaN 变成 "nan"，空编码曾一起退化成同一个键。"""
    loader = load(write_catalog(tmp_path, 课程编码=["G0001", None, ""]))

    keys = identity_keys(loader)
    assert len(set(keys)) == 3
    assert keys[0][0] == "G0001"
    assert all("nan" not in code for code, _ in keys)


def test_real_codes_are_left_alone(tmp_path):
    loader = load(write_catalog(tmp_path, 课程编码=["G0001", "G0002", "G0003"]))

    assert [code for code, _ in identity_keys(loader)] == ["G0001", "G0002", "G0003"]
    assert loader.column_warnings == []


def test_duplicate_identity_keys_are_reported(tmp_path):
    loader = load(write_catalog(tmp_path, 课程编码=["G0001", "G0001", "G0003"]))

    assert any("重复" in warning for warning in loader.column_warnings)


def test_warnings_do_not_leak_between_loads(tmp_path):
    """同一个 loader 复用时，上一份表的警告不能留到下一份。"""
    loader = CourseDataLoader()
    assert loader.load_from_excel(write_catalog(tmp_path)) is True  # 缺编码列，会产生警告
    assert loader.column_warnings != []

    clean = tmp_path / "clean.xlsx"
    pd.DataFrame({**BASE_ROWS, "课程编码": ["G0001", "G0002", "G0003"]}).to_excel(clean, index=False)
    assert loader.load_from_excel(str(clean)) is True

    assert loader.column_warnings == []


# ── 走真实 API 的端到端覆盖 ────────────────────────────────────────────────────

pytest.importorskip("fastapi.testclient", reason="fastapi TestClient unavailable")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PUMC_DATA_DIR", str(tmp_path / "data"))
    from fastapi.testclient import TestClient
    from web_backend.server import app

    with TestClient(app) as test_client:
        test_client.delete("/api/selected-courses")
        yield test_client


def import_catalog(client, path):
    with open(path, "rb") as handle:
        response = client.post(
            "/api/courses/load", files={"file": ("catalog.xlsx", handle.read())}
        )
    assert response.status_code == 200
    return client.get("/api/courses").json()


def greyed_out_names(client, catalog):
    """复刻 CoursesPage.tsx 的『已选』判定：(course_code, class_index)。"""
    selected = client.get("/api/selected-courses").json()
    return [
        course["course_name"]
        for course in catalog
        if any(
            item["course"]["course_code"] == course["course_code"]
            and item["class_index"] == course["class_index"]
            for item in selected
        )
    ]


def test_adding_one_course_greys_out_only_that_course(client, tmp_path):
    catalog = import_catalog(client, write_catalog(tmp_path))  # 缺编码列的表

    target = catalog[2]
    response = client.post(
        "/api/selected-courses",
        data={"course_code": target["course_code"], "class_index": target["class_index"]},
    )

    assert response.status_code == 200
    # 点哪门就是哪门，不再静默换成第一门
    assert response.json()["course"]["course_name"] == target["course_name"]
    assert greyed_out_names(client, catalog) == [target["course_name"]]


def test_a_second_course_can_still_be_added(client, tmp_path):
    catalog = import_catalog(client, write_catalog(tmp_path))

    for course in catalog[:2]:
        response = client.post(
            "/api/selected-courses",
            data={"course_code": course["course_code"], "class_index": course["class_index"]},
        )
        assert response.status_code == 200, response.json()

    assert len(client.get("/api/selected-courses").json()) == 2


def test_ambiguous_code_is_rejected_instead_of_adding_the_wrong_course(client, tmp_path):
    path = write_catalog(tmp_path, 课程编码=["G0001", "G0001", "G0003"])
    catalog = import_catalog(client, path)

    duplicated = next(course for course in catalog if course["course_name"] == "分子生物学")
    response = client.post(
        "/api/selected-courses",
        data={"course_code": duplicated["course_code"], "class_index": duplicated["class_index"]},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "医学统计学" in detail and "分子生物学" in detail
    assert client.get("/api/selected-courses").json() == []
