"""缺「课程类别」列的课表必须走手工设类别流程，而不是被静默归桶。

真实教务导出的一览表列结构并不统一：附件3-2025下 就没有「课程类别」列。
这类表照样要能导入，然后由用户在课程页手工设类别——这是产品既有的
兼容机制，不能因为缺列就把课程悄悄塞进某个学分桶。

历史 bug：_clean_data 给缺失的「课程类别」填默认值 "选修课"，
该值命中 _auto_assign_category 的 "选修" 分支 → 全部归入
「选修课 - 学位选修」。于是公共必修课的学分被算进学位选修，
UI 显示为已设置好，用户完全看不到需要修正。
"""

import io
import contextlib

import pandas as pd
import pytest

from core.data_loader import CourseDataLoader
from core.models import SelectedCourse

ALL_SIX_CATEGORIES = {
    "公共必修课 - 公共必修",
    "公共必修课 - 公共必修（二选一）",
    "选修课 - 限制性选修",
    "选修课 - 通识选修",
    "选修课 - 学位选修",
    "学位必修课（核心课）",
}

#: 真实一览表里「课程类别」的确切取值（注意是「限制选修课」，无“性”字）
BASE_ROWS = [
    {
        "课程编码": "PUBL38001", "课程名称": "中国马克思主义与当代", "开课院系": "马克思主义学院",
        "课程类别": "公共必修课", "班次": 1, "校区": "东单校区", "任课教师": "张",
        "学分": 2.0, "学时": 36.0,
        "星期": 1, "开始节次": 1, "结束节次": 4, "周次": "1-16",
    },
    {
        "课程编码": "PHAR08062", "课程名称": "药事管理法规和药品注册管理", "开课院系": "药物研究所",
        "课程类别": "限制选修课", "班次": 1, "校区": "东单校区", "任课教师": "王",
        "学分": 1.5, "学时": 30.0,
        "星期": 2, "开始节次": 1, "结束节次": 4, "周次": "1-16",
    },
    {
        "课程编码": "CULT05003", "课程名称": "世界医学荟萃", "开课院系": "人文学院",
        "课程类别": "通识选修课", "班次": 1, "校区": "东单校区", "任课教师": "李",
        "学分": 1.0, "学时": 20.0,
        "星期": 3, "开始节次": 5, "结束节次": 8, "周次": "1-16",
    },
]


def _load(tmp_path, rows, *, drop_category: bool) -> CourseDataLoader:
    frame = pd.DataFrame(rows)
    if drop_category:
        frame = frame.drop(columns=["课程类别"])
    path = tmp_path / "catalog.xlsx"
    frame.to_excel(path, index=False)

    loader = CourseDataLoader()
    with contextlib.redirect_stdout(io.StringIO()):
        assert loader.load_from_excel(str(path)) is True
    return loader


def _as_selected(course) -> SelectedCourse:
    return SelectedCourse(course, course.class_num, [], course.is_online, "")


def _is_unset(selected: SelectedCourse) -> bool:
    return str(selected.custom_category).strip().lower() in ("", "nan")


def test_missing_category_column_still_imports(tmp_path):
    """缺列不能导致导入失败——这类表必须兼容。"""
    loader = _load(tmp_path, BASE_ROWS, drop_category=True)

    assert len(loader.get_courses()) == len(BASE_ROWS)
    assert any("课程类别" in warning for warning in loader.column_warnings)


def test_missing_category_column_leaves_every_course_unset(tmp_path):
    """缺列时一律「类别待设置」，绝不能静默归入学位选修。"""
    loader = _load(tmp_path, BASE_ROWS, drop_category=True)

    for course in loader.get_courses():
        selected = _as_selected(course)
        assert _is_unset(selected), (
            f"{course.code} 被静默归入 {selected.custom_category!r}，"
            "用户不会收到任何提示"
        )


def test_missing_category_column_offers_all_six_options(tmp_path):
    """没有原始类别就无法缩小范围，下拉必须给全六项。

    只给「学位选修 / 核心课」的话，用户根本选不到公共必修或通识选修。
    """
    loader = _load(tmp_path, BASE_ROWS, drop_category=True)

    for course in loader.get_courses():
        options = set(_as_selected(course).get_available_categories())
        assert options == ALL_SIX_CATEGORIES, f"{course.code} 只给了 {options}"


def test_public_required_still_needs_manual_choice(tmp_path):
    """有类别列时，公共必修仍要用户手选——「二选一」无法自动判定。"""
    loader = _load(tmp_path, BASE_ROWS, drop_category=False)

    course = next(c for c in loader.get_courses() if c.code == "PUBL38001")
    selected = _as_selected(course)

    assert _is_unset(selected), "公共必修应保持待设置，交由用户区分是否二选一"
    assert set(selected.get_available_categories()) == {
        "公共必修课 - 公共必修",
        "公共必修课 - 公共必修（二选一）",
    }


@pytest.mark.parametrize(
    "code,source_label,expected_category",
    [
        # 真实表写的是「限制选修课」，此前前端只匹配「限制性选修」导致落错桶
        ("PHAR08062", "限制选修课", "选修课 - 限制性选修"),
        ("CULT05003", "通识选修课", "选修课 - 通识选修"),
    ],
)
def test_known_source_labels_auto_assign(tmp_path, code, source_label, expected_category):
    """有明确类别的课自动归位，不该打扰用户。"""
    loader = _load(tmp_path, BASE_ROWS, drop_category=False)

    course = next(c for c in loader.get_courses() if c.code == code)
    selected = _as_selected(course)

    assert course.category == source_label
    assert selected.custom_category == expected_category
    assert selected.get_available_categories() == [expected_category]


def test_blank_category_cell_behaves_like_missing_column(tmp_path):
    """列在但某行为空，同样应待设置（而非按空串猜成选修）。"""
    rows = [dict(BASE_ROWS[0], 课程类别=""), dict(BASE_ROWS[1])]
    loader = _load(tmp_path, rows, drop_category=False)

    blank = next(c for c in loader.get_courses() if c.code == "PUBL38001")
    selected = _as_selected(blank)

    assert _is_unset(selected)
    assert set(selected.get_available_categories()) == ALL_SIX_CATEGORIES
