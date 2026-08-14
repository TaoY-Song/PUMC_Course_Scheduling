"""Regression coverage for course-calendar fields imported from Excel."""

import pandas as pd

from core.data_loader import CourseDataLoader
from core.services.course_supplement_service import CourseSupplementService


def test_excel_time_columns_create_course_time_slot(tmp_path):
    path = tmp_path / "courses.xlsx"
    pd.DataFrame(
        [
            {
                "课程编码": "MED101",
                "课程名称": "临床导论",
                "开课院系": "临床学院",
                "课程类别": "选修课",
                "班次": 1,
                "校区": "东单",
                "任课教师": "张老师",
                "学分": 2,
                "学时": 32,
                "星期": "周三",
                "开始节次": 3,
                "结束节次": 4,
                "周次": "1-8,10,12-13",
            }
        ]
    ).to_excel(path, index=False)

    loader = CourseDataLoader()
    assert loader.load_from_excel(str(path)) is True

    course = loader.get_courses()[0]
    assert len(course.time_slots) == 1
    slot = course.time_slots[0]
    assert (slot.weekday, slot.start_section, slot.end_section) == (3, 3, 4)
    assert slot.weeks == [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 13]


def test_excel_supports_two_weekly_meetings_for_high_credit_course(tmp_path):
    path = tmp_path / "high-credit-course.xlsx"
    pd.DataFrame(
        [
            {
                "课程编码": "MED401",
                "课程名称": "高级临床研究",
                "开课院系": "临床学院",
                "课程类别": "学位专业课",
                "班次": 1,
                "校区": "东单校区",
                "任课教师": "王老师",
                "学分": 4,
                "学时": 64,
                "星期": "周一",
                "开始节次": 1,
                "结束节次": 4,
                "周次": "1-8",
                "星期2": "周四",
                "开始节次2": 5,
                "结束节次2": 8,
                "周次2": "1-8",
            }
        ]
    ).to_excel(path, index=False)

    loader = CourseDataLoader()
    assert loader.load_from_excel(str(path)) is True

    slots = loader.get_courses()[0].time_slots
    assert len(slots) == 2
    assert (slots[0].weekday, slots[0].start_section, slots[0].end_section) == (1, 1, 4)
    assert (slots[1].weekday, slots[1].start_section, slots[1].end_section) == (4, 5, 8)
    assert slots[0].weeks == slots[1].weeks == list(range(1, 9))


def test_supplement_service_always_emits_downloadable_result(tmp_path, monkeypatch):
    """无缺失课程时，底层 tester 会早退；Web 仍必须有结果文件可下载。"""
    schedule = tmp_path / "schedule.xlsx"
    schedule.write_bytes(b"PK-valid-schedule-placeholder")
    catalog = tmp_path / "catalog.xlsx"
    catalog.write_bytes(b"catalog-placeholder")
    output_name = "supplement-result.xlsx"

    class CompleteScheduleTester:
        def __init__(self):
            self.added_courses = []
            self.failed_courses = []
            self.stats = {
                "successfully_added": 0,
                "failed_to_add": 0,
                "missing_courses": 0,
            }
            self.course_list_file = ""
            self.schedule_result_file = ""
            self.output_file = ""

        def run(self):
            # 模拟 scripts.CourseSupplementTester 的“没有缺失课程”早退：
            # 不创建 self.output_file。
            return None

    service = CourseSupplementService(
        log_file_path=str(tmp_path / "supplement.log"),
        output_file_name=output_name,
    )
    monkeypatch.setattr(service, "validate_files", lambda *_: (True, "ok"))
    monkeypatch.setattr(
        "core.services.course_supplement_service._get_course_supplement_tester",
        lambda: CompleteScheduleTester,
    )

    result = service.run_supplement_test(str(schedule), str(catalog))

    output = tmp_path / output_name
    assert result["success"] is True
    assert result["output_file"] == str(output)
    assert output.read_bytes() == schedule.read_bytes()


def test_online_course_does_not_import_physical_time_slot(tmp_path):
    path = tmp_path / "online.xlsx"
    pd.DataFrame(
        [
            {
                "课程编码": "WEB101",
                "课程名称": "线上课程",
                "开课院系": "教务处",
                "课程类别": "选修课",
                "班次": 1,
                "校区": "线上",
                "任课教师": "李老师",
                "学分": 1,
                "学时": 16,
                "是否线上": "是",
                "星期": 1,
                "开始节次": 1,
                "结束节次": 2,
            }
        ]
    ).to_excel(path, index=False)

    loader = CourseDataLoader()
    assert loader.load_from_excel(str(path)) is True
    assert loader.get_courses()[0].time_slots == []
