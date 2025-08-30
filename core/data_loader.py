#!/usr/bin/env python3
"""
数据加载和处理逻辑
负责从Excel文件加载课程数据，进行验证、清洗和转换
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import Course


class CourseDataLoader:
    """课程数据加载器"""

    def __init__(self):
        self.courses: List[Course] = []
        self.load_report: Dict[str, Any] = {}

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
            print(f"❌ Excel文件缺少必要列: {missing_columns}")
            print("请确保Excel文件包含以下列:")
            for col in required_columns:
                print(f"  - {col}")
            return False

        print("✓ Excel文件列验证通过")
        return True

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        df = df.copy()

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

        return df

    def _create_course_from_row(self, row) -> Optional[Course]:
        """从数据行创建Course对象"""
        try:
            # 处理线上状态信息
            is_online_str = str(row.get("是否线上", "否")).strip()
            is_online = is_online_str == "是"

            # 处理自定义类别信息
            custom_category = str(row.get("自定义类别", "")).strip()

            return Course(
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
        except Exception as e:
            print(f"创建课程对象失败: {e}")
            return None

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
