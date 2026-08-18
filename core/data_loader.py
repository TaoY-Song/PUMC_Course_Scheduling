#!/usr/bin/env python3
"""
数据加载和处理逻辑
负责从Excel文件加载课程数据，进行验证、清洗和转换
"""

import re

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import Course, TimeSlot

# 教务处各学期导出的一览表表头并不统一，同一个字段常换几种写法。
# 这里只覆盖身份列「课程编码」：认不出来会导致整列编码退化成同一个值，
# 后果是全表课程一起变灰、加课加错门。其余列认不出来只是显示成默认值，
# 危害小得多，且在看不到真实表格的情况下乱加别名反而可能改错语义，
# 所以留给维护者按实际表头补。
# 只在规范列名缺席时才用别名顶上，避免把真有区别的两列混在一起。
COLUMN_ALIASES: Dict[str, tuple] = {
    "课程编码": ("课程编号", "课程代码", "课程号", "课程代号", "course_code"),
}

# 缺少课程编码时按行号生成的占位编码前缀。
AUTO_CODE_PREFIX = "AUTO"


class CourseDataLoader:
    """课程数据加载器"""

    def __init__(self):
        self.courses: List[Course] = []
        self.load_report: Dict[str, Any] = {}
        self.column_warnings: List[str] = []

    def load_from_excel(self, file_path: str) -> bool:
        """从Excel文件加载课程数据"""
        try:
            print(f"正在加载课程数据: {file_path}")

            # 检查文件是否存在
            if not Path(file_path).exists():
                print(f"❌ 文件不存在: {file_path}")
                return False

            # 读取Excel文件
            df = pd.read_excel(file_path)
            print(f"✓ 成功读取Excel文件，共 {len(df)} 条记录")

            # 同一个 loader 可能被复用来加载第二份表，警告不能沿用上一次的。
            self.column_warnings = []

            # 先把别名表头改写成规范列名，再判断哪些列真的缺失
            df = self._normalize_column_names(df)

            # 验证必要列
            if not self._validate_columns(df):
                return False

            # 清洗数据
            df = self._clean_data(df)

            # 转换为Course对象
            self.courses = []
            failed_count = 0

            for index, row in df.iterrows():
                try:
                    course = self._create_course_from_row(row)
                    if course:
                        self.courses.append(course)
                except Exception as e:
                    failed_count += 1
                    print(f"⚠️ 第 {index + 1} 行数据转换失败: {e}")

            # 生成加载报告
            self._generate_load_report(len(df), failed_count)

            print(f"✅ 数据加载完成: 成功加载 {len(self.courses)} 门课程")
            if failed_count > 0:
                print(f"⚠️ {failed_count} 条记录加载失败")

            return True

        except Exception as e:
            print(f"❌ 加载课程数据失败: {e}")
            return False

    def _validate_columns(self, df: pd.DataFrame) -> bool:
        """验证必要列是否存在"""
        required_columns = [
            "课程编码",
            "课程名称",
            "开课院系",
            "课程类别",
            "班次",
            "校区",
            "任课教师",
            "学分",
            "学时",
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            # 用 append 而不是覆盖：_normalize_column_names 可能已经记了别名映射。
            for col in missing_columns:
                if col == "课程编码":
                    # 这一列不走「填默认值」那条路，_ensure_unique_course_codes
                    # 会按行号生成唯一编码并给出更准确的警告，别报两遍。
                    continue
                warning = f"缺少列 '{col}'，已使用默认值"
                self.column_warnings.append(warning)
                print(f"⚠️ {warning}")
            print("  将使用默认值继续处理...")

        print("✓ Excel文件列验证通过")
        return True

    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """把常见的表头别名改写成规范列名。

        学校发的一览表里「课程编码」经常写作「课程编号」。识别不出来就会
        走缺列兜底，整列编码退化成同一个值——那正是全表课程一起变灰的起点。
        """
        df = df.copy()
        df.columns = [str(column).strip() for column in df.columns]

        renames: Dict[str, str] = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            if canonical in df.columns:
                continue
            for alias in aliases:
                if alias in df.columns and alias not in renames:
                    renames[alias] = canonical
                    warning = f"列 '{alias}' 已按 '{canonical}' 处理"
                    self.column_warnings.append(warning)
                    print(f"  ↪ {warning}")
                    break

        return df.rename(columns=renames) if renames else df

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        df = df.copy()

        # 课程编码是身份列，必须逐行唯一，不能和下面的展示列一样填常量。
        df = self._ensure_unique_course_codes(df)

        # 为缺失的列添加默认值
        # 注意：课程类别留空字符串，不能编造 "选修课"。
        # 填 "选修课" 会命中 _auto_assign_category 的 "选修" 分支，
        # 把课静默归入「选修课 - 学位选修」——公共必修课的学分会被
        # 算进学位选修桶，而 UI 显示为已设置好，用户无从发现。
        # 留空则走 "nan" 分支，正常呈现为「类别待设置」等用户手选。
        defaults = {
            "课程名称": "未知课程",
            "开课院系": "未知院系",
            "课程类别": "",
            "班次": 1,
            "校区": "校本部",
            "任课教师": "待定",
            "学分": 0.0,
            "学时": 0.0,
        }
        
        for col, default_value in defaults.items():
            if col not in df.columns:
                df[col] = default_value
                print(f"  ⚠️ 列 '{col}' 使用默认值: {default_value}")

        # 去除字符串列的前后空格
        string_columns = [
            "课程编码",
            "课程名称",
            "开课院系",
            "课程类别",
            "校区",
            "任课教师",
        ]
        for col in string_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # 处理数值列
        df["班次"] = pd.to_numeric(df["班次"], errors="coerce").fillna(1).astype(int)
        df["学分"] = (
            pd.to_numeric(df["学分"], errors="coerce").fillna(0.0).astype(float)
        )
        df["学时"] = (
            pd.to_numeric(df["学时"], errors="coerce").fillna(0.0).astype(float)
        )

        # 处理选课说明列（如果存在）
        if "选课说明" in df.columns:
            df["选课说明"] = df["选课说明"].fillna("").astype(str)

        # 过滤无效数据
        df = df.dropna(subset=["课程编码", "课程名称"])
        df = df[df["课程编码"].str.strip() != ""]
        df = df[df["课程名称"].str.strip() != ""]

        self._warn_about_duplicate_keys(df)

        return df

    def _ensure_unique_course_codes(self, df: pd.DataFrame) -> pd.DataFrame:
        """保证「课程编码」这一列真的能当身份用。

        目录去重、按编码查课、前端「已选」判断全靠这一列。整列填同一个常量
        （原先的 ``"UNKNOWN"``）会让所有课程共用一个键：加入任意一门课，前端
        整张表一起判为「已选」变灰；后端 ``find_courses`` 也只会返回第一条，
        于是点 A 加进去的是 B。缺失/空白一律按行号生成唯一占位编码。
        """
        df = df.copy()

        def auto_code(position: int) -> str:
            # +2：Excel 第 1 行是表头，数据从第 2 行开始，方便用户回表核对。
            return f"{AUTO_CODE_PREFIX}{position + 2:04d}"

        if "课程编码" not in df.columns:
            df["课程编码"] = [auto_code(position) for position in range(len(df))]
            warning = f"缺少列 '课程编码'，已按行号生成占位编码（{auto_code(0)} 起）"
            self.column_warnings.append(warning)
            print(f"  ⚠️ {warning}")
            return df

        codes = df["课程编码"].astype(str).str.strip()
        # astype(str) 会把 NaN 变成字符串 "nan"，后面的空值过滤就拦不住了，
        # 多行空编码会一起退化成同一个 "nan"——和常量兜底是同一个毛病。
        blank = df["课程编码"].isna() | codes.isin(("", "nan", "NaN", "None", "<NA>"))
        if blank.any():
            fallback = pd.Series(
                [auto_code(position) for position in range(len(df))], index=df.index
            )
            codes = codes.mask(blank, fallback)
            warning = f"{int(blank.sum())} 行的课程编码为空，已按行号生成占位编码"
            self.column_warnings.append(warning)
            print(f"  ⚠️ {warning}")

        df["课程编码"] = codes
        return df

    def _warn_about_duplicate_keys(self, df: pd.DataFrame) -> None:
        """「课程编码 + 班次」在表内撞车时提醒用户。

        这一对是全链路的身份键，重复的两门课在选课界面会互相牵连。
        源数据的真伪只有用户能判断，这里只报告，不自作主张改编码。
        """
        if df.empty:
            return

        duplicated = df.duplicated(subset=["课程编码", "班次"], keep=False)
        if not duplicated.any():
            return

        pairs = [
            f"{code} 班次{class_num}"
            for code, class_num in (
                df.loc[duplicated, ["课程编码", "班次"]].drop_duplicates().itertuples(index=False)
            )
        ]
        preview = "、".join(pairs[:5]) + ("…" if len(pairs) > 5 else "")
        warning = f"{len(pairs)} 组「课程编码+班次」在表内重复（{preview}），选课时会互相干扰"
        self.column_warnings.append(warning)
        print(f"  ⚠️ {warning}")

    def _create_course_from_row(self, row) -> Optional[Course]:
        """从数据行创建 Course，并尽可能保留课程表中的时间信息。"""
        try:
            is_online = str(row.get("是否线上", "否")).strip() == "是"
            custom_category = str(row.get("自定义类别", "")).strip()
            course = Course(
                code=str(row["课程编码"]).strip(),
                name=str(row["课程名称"]).strip(),
                department=str(row["开课院系"]).strip(),
                category=str(row["课程类别"]).strip(),
                class_num=int(row["班次"]),
                campus=str(row["校区"]).strip(),
                teacher=str(row["任课教师"]).strip(),
                credits=float(row["学分"]),
                hours=float(row["学时"]),
                description=str(row.get("选课说明", "")).strip(),
                is_online=is_online,
                custom_category=custom_category,
            )
            # Course 是课程目录元数据，时间属于具体班次。目录阶段暂存该
            # 字段，state.add_selected_course 会复制到 SelectedCourse。
            course.time_slots = [] if is_online else self._parse_time_slots(row)
            return course
        except Exception as e:
            print(f"创建课程对象失败: {e}")
            return None

    def _parse_time_slots(self, row) -> List[TimeSlot]:
        """解析常见星期/节次/周次列，支持一门课同周两次授课。"""
        slots: List[TimeSlot] = []
        for suffix in ("", "2", "二"):
            day_value = self._first_value(
                row,
                *(f"{column}{suffix}" for column in ("星期", "周几", "上课星期", "day_of_week", "weekday")),
            )
            start_value = self._first_value(
                row,
                *(f"{column}{suffix}" for column in ("开始节次", "起始节次", "start_period", "start_section")),
            )
            end_value = self._first_value(
                row,
                *(f"{column}{suffix}" for column in ("结束节次", "终止节次", "end_period", "end_section")),
            )
            if all(self._is_empty(value) for value in (day_value, start_value, end_value)):
                continue
            if any(self._is_empty(value) for value in (day_value, start_value, end_value)):
                continue

            try:
                weeks_value = self._first_value(
                    row,
                    *(f"{column}{suffix}" for column in ("周次", "教学周", "weeks")),
                )
                slots.append(
                    TimeSlot(
                        weekday=self._parse_weekday(day_value),
                        start_section=int(float(start_value)),
                        end_section=int(float(end_value)),
                        weeks=self._parse_weeks(weeks_value) or list(range(1, 21)),
                    )
                )
            except (TypeError, ValueError):
                continue
        return slots

    @staticmethod
    def _first_value(row, *columns: str):
        for column in columns:
            if column in row and not CourseDataLoader._is_empty(row[column]):
                return row[column]
        return None

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or pd.isna(value) or str(value).strip() == ""

    @staticmethod
    def _parse_weekday(value: Any) -> int:
        text = str(value).strip().lower()
        aliases = {
            "周一": 1, "星期一": 1, "monday": 1,
            "周二": 2, "星期二": 2, "tuesday": 2,
            "周三": 3, "星期三": 3, "wednesday": 3,
            "周四": 4, "星期四": 4, "thursday": 4,
            "周五": 5, "星期五": 5, "friday": 5,
            "周六": 6, "星期六": 6, "saturday": 6,
            "周日": 7, "周天": 7, "星期日": 7, "sunday": 7,
        }
        if text in aliases:
            return aliases[text]
        weekday = int(float(value))
        if weekday not in range(1, 8):
            raise ValueError("星期必须在 1 到 7 之间")
        return weekday

    @staticmethod
    def _parse_weeks(value: Any) -> List[int]:
        if CourseDataLoader._is_empty(value):
            return []
        # 教务导出常带“第…周”包裹（如「第2-18周」）。不剔的话
        # 整个表达式都匹配不上，静默返回空周次——课变成没时间。
        text = str(value).strip()
        text = re.sub(r"^第", "", text)
        text = re.sub(r"周(次)?$", "", text)
        weeks = set()
        for part in re.split(r"[,，、;；\s]+", text.strip()):
            if not part:
                continue
            # 单个区间也可能自带包裹（如「1-8周,10周」）
            piece = re.sub(r"^第", "", part)
            piece = re.sub(r"周(次)?$", "", piece).strip()
            if not piece:
                continue
            match = re.fullmatch(r"(\d+)\s*[-~—–至]\s*(\d+)", piece)
            if match:
                start, end = map(int, match.groups())
                weeks.update(range(min(start, end), max(start, end) + 1))
            elif piece.isdigit():
                weeks.add(int(piece))
        return sorted(week for week in weeks if week > 0)

    def _generate_load_report(self, total_records: int, failed_count: int):
        """生成加载报告"""
        self.load_report = {
            "total_records": total_records,
            "successful_records": len(self.courses),
            "failed_records": failed_count,
            "success_rate": f"{(len(self.courses) / total_records * 100):.1f}%"
            if total_records > 0
            else "0%",
            "categories": list(set(course.category for course in self.courses)),
            "departments": list(set(course.department for course in self.courses)),
            "campuses": list(set(course.campus for course in self.courses)),
            "column_warnings": self.column_warnings,
        }

    def get_courses(self) -> List[Course]:
        """获取加载的课程列表"""
        return self.courses

    def get_load_report(self) -> Dict[str, Any]:
        """获取加载报告"""
        return self.load_report

    def display_summary(self):
        """显示数据摘要"""
        if not self.courses:
            print("❌ 没有加载任何课程数据")
            return

        print("\n" + "=" * 60)
        print("📊 课程数据摘要")
        print("=" * 60)
        print(f"总课程数: {len(self.courses)}")
        print(f"课程类别: {len(self.load_report['categories'])} 个")
        print(f"开课院系: {len(self.load_report['departments'])} 个")
        print(f"校区: {len(self.load_report['campuses'])} 个")

        print("\n课程类别分布:")
        category_count = {}
        for course in self.courses:
            category_count[course.category] = category_count.get(course.category, 0) + 1

        for category, count in sorted(category_count.items()):
            print(f"  {category}: {count} 门")

        print("\n校区分布:")
        campus_count = {}
        for course in self.courses:
            campus_count[course.campus] = campus_count.get(course.campus, 0) + 1

        for campus, count in sorted(campus_count.items()):
            print(f"  {campus}: {count} 门")
