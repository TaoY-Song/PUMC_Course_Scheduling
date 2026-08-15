# 测试文件索引

每次新增测试前查这里，找到对应文件直接加进去，不用新建文件。

---

## 往哪里加

| 想测的内容 | 加到哪里 |
|-----------|---------|
| 时间冲突、半天块、校区约束 | `test_campus_constraints.py` |
| 学分溢出上限、救场逻辑、溢出比例 | `test_credit_efficiency.py` |
| 时间段键的生成与冲突检测 | `test_time_slot_keys.py` |
| 求解器结构、候选池大小、完整搜索/穷举对比 | `test_solver_limits.py` |
| 求解器已删除的功能（CP-SAT、死代码） | `test_single_solver.py` |
| SchedulingConfig 字段、验证、序列化、DTO 映射 | `test_config_and_dto.py` |
| Excel 时间列解析、周次写法、缺列容错 | `test_data_loader_times.py` 或 `test_category_compatibility.py` |
| 类别映射、getCategoryOptions、前端类别匹配 | `test_category_compatibility.py` |
| 排课结果评分、score 字段 | `test_evaluator_scores.py` |
| 调度服务层（generate_schedules 上层） | `test_scheduling_service.py` |
| 任务运行时、取消竞态、并发提交 | `test_task_runtime.py` |
| REST API 端点、HTTP 请求/响应契约 | `test_api_scheduling_flow.py` |
| EventManager、事件跨线程传递、WebSocket | `test_web_events.py` |
| 打包路径（is_frozen、resource_path、user_data_dir） | `test_app_paths.py` |

---

## 什么时候才新建文件

满足以下任意一条：

1. 测的是一个**全新的独立模块**，现有文件没有合适的位置
2. 预计新增超过 **10 个测试**，且主题与现有文件明显不同
3. 需要用到与现有测试**完全不同的 fixture 或外部资源**（如真实浏览器、数据库）

否则直接加到现有文件里，哪怕加 1-2 个测试。

---

## 共享 fixture（conftest.py）

| Fixture | 用途 |
|---------|------|
| `make_course(code, weekday, start_section, *, campus, credits, category, online, weeks, end_section)` | 构造一门带时间段的 SelectedCourse |
| `credit_manager(required, completed)` | 只设置了学位选修要求的 CreditManager（其他类别清零） |
| `event_recorder` | 记录所有事件的轻量 EventManager |

需要新的公共 fixture 就加到 `conftest.py`，不要在每个测试文件里重复定义。
