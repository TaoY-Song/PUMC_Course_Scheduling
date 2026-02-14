# PUMC智能排课系统 - Web版本功能增强计划文档

**文档版本**：1.0  
**创建日期**：2026年2月14日  
**项目**：PUMC Course Scheduling Web vs Qt Feature Parity Analysis  
**目的**：详细对比Web版本与Qt版本功能差异，制定增强计划

---

## 一、分析背景与目的

### 1.1 项目概述

PUMC智能排课系统是一个基于OR-Tools约束求解器的课程调度系统，提供两个版本：

- **Qt版本**：PyQt5桌面应用程序，功能完整
- **Web版本**：React + FastAPI Web应用程序，部分功能尚未完善

### 1.2 分析目的

通过代码层面的深入分析，明确两个版本的功能差异，为Web版本的功能完善提供详细的实现计划。

### 1.3 分析方法

- 源代码探索：Qt版本（`ui/`、`core/`、`scripts/`）和Web版本（`web/src/`、`web_backend/`）
- API端点审查：验证后端接口完整性
- 组件实现对照：对比UI组件实现程度

---

## 二、Qt版本功能清单（完整版）

经过深入分析，Qt版本具备以下功能模块：

### 2.1 数据加载模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| Excel文件加载 | `core/data_loader.py` | 支持.xls和.xlsx格式 |
| 列验证 | `CourseDataLoader._validate_columns()` | 验证必需列存在 |
| 数据清洗 | `CourseDataLoader._clean_data()` | 去除无效记录 |
| 线上课程识别 | `CourseDataLoader` | 读取"是否线上"列，关键词匹配备用 |
| 自定义类别 | `CourseDataLoader` | 读取"自定义类别"列 |
| 课程索引 | `CourseDataLoader` | 按课程编码建立索引 |
| 加载报告 | `CourseDataLoader.get_load_report()` | 成功率、分布统计 |

### 2.2 课程管理模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 课程搜索 | `ui/main_window.py` | 按课程编码搜索 |
| 课程信息显示 | `ui/main_window.py` | 显示名称、教师、校区、学分等 |
| 班次选择 | `ui/main_window.py` | QComboBox下拉选择 |
| 线上课程勾选 | `ui/main_window.py` | 自动检测+手动调整 |
| 添加课程 | `ui/main_window.py` | 添加到已选列表 |
| 移除课程 | `ui/main_window.py` | 从已选列表移除 |
| 清空所有 | `ui/main_window.py` | 清空所有已选课程 |
| 课程表格 | `ui/main_window.py` | 10列详细信息表格 |

### 2.3 时间段配置模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 时间段对话框 | `ui/dialogs.py` - `TimeSlotDialog` | 完整配置界面 |
| 星期选择 | `TimeSlotDialog` | 周一至周日下拉框 |
| 节次选择 | `TimeSlotDialog` | 开始/结束节次（1-10） |
| 周次选择 | `TimeSlotDialog` | 20个可点击按钮（4行×5列） |
| 全选功能 | `TimeSlotDialog.select_all_weeks()` | 快捷全选 |
| 清空功能 | `TimeSlotDialog.clear_all_weeks()` | 快捷清空 |
| 视觉反馈 | `TimeSlotDialog.update_week_button_styles()` | 绿色=选中，灰色=未选中 |
| 输入验证 | `TimeSlotDialog.add_time_slot()` | 节次顺序、周次数量验证 |

### 2.4 学分类别管理模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 6种标准类别 | `core/models.py` - `SelectedCourse` | 见下方列表 |
| 自动分配 | `SelectedCourse._auto_assign_category()` | 根据原始类别自动映射 |
| 行内编辑 | `ui/main_window.py` - `CategoryComboDelegate` | 表格中直接修改 |
| 类别设置对话框 | `ui/dialogs.py` - `CategorySettingDialog` | 详细配置界面 |

**6种标准学分类别**：

1. 公共必修课 - 公共必修（4.0学分）
2. 公共必修课 - 公共必修（二选一）（1.0学分）
3. 选修课 - 限制性选修（1.0学分）
4. 选修课 - 通识选修（1.0学分）
5. 选修课 - 学位选修（8.0学分）
6. 学位必修课（核心课）（11.0学分）

### 2.5 学分管理模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 学分管理器 | `core/credit_manager.py` - `CreditManager` | 6种类别学分管理 |
| 学分要求设置 | `CreditManager.set_required_credits()` | 设置最低学分 |
| 已修学分设置 | `CreditManager.set_completed_credits()` | 手动设置已修学分 |
| 学分统计 | `CreditManager.get_categories_summary()` | 各类别完成情况 |
| 重置默认 | `ui/dialogs.py` - `CreditSettingsDialog` | 恢复默认设置 |

### 2.6 排课算法模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| OR-Tools集成 | `core/scheduling/engine.py` | Google CP-SAT求解器 |
| 三阶段排课 | `SchedulingEngine.execute()` | 见下方说明 |
| 学分约束模式 | `core/scheduling/config.py` - `CreditConstraintMode` | REQUIRED/OPTIMAL |
| 校区冲突模式 | `core/scheduling/config.py` - `CampusConflictMode` | DAILY/PERIOD/DISABLED |
| 时间冲突检测 | `core/scheduling/constraints.py` - `ConstraintChecker` | |
| 校区冲突检测 | `ConstraintChecker.check_campus_conflicts()` | |
| 结果评分 | `core/scheduling/evaluator.py` - `ScheduleEvaluator` | |

**三阶段排课**：

1. 阶段1：处理线上课程（无时间约束，高优先级）
2. 阶段2：OR-Tools约束满足求解（有时间课程）
3. 阶段3：结果合并与评分

### 2.7 导入导出模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 导出已选课程 | `core/import_export.py` - `SelectedCourseExporter` | 3个Sheet |
| 导入已选课程 | `core/import_export.py` - `SelectedCourseImporter` | 完整验证 |
| 导出排课结果 | `SelectedCourseExporter.export_scheduling_result()` | |
| 周课表导出 | `_create_weekly_schedule_sheet()` | 5行×7列表格 |
| 统计信息导出 | `_create_statistics_sheet()` | 按类别/校区统计 |

### 2.8 课程补充测试模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 补充测试工具 | `scripts/course_supplement_test.py` - `CourseSupplementTester` | |
| 遗漏课程识别 | `CourseSupplementTester.find_missing_courses()` | |
| 约束添加 | `CourseSupplementTester.attempt_add_course()` | 基于约束尝试添加 |
| 统计报告 | `CourseSupplementTester.print_statistics()` | 成功率统计 |
| 结果对话框 | `ui/dialogs/supplement_result_dialog.py` | 结果展示 |

### 2.9 UI交互模块

| 功能 | 实现文件 | 说明 |
|------|----------|------|
| 异步加载 | `ui/main_window.py` - `CourseLoadThread` | QThread后台线程 |
| 进度显示 | `CourseLoadThread.progress` 信号 | |
| 状态消息 | `ui/main_window.py` | 多种状态提示 |
| 错误对话框 | `QMessageBox` | 错误处理 |
| 日志管理 | `app.py` - `LogManager` | 控制台+文件双输出 |

---

## 三、Web版本功能清单（当前版）

### 3.1 页面/路由

| 页面 | Tab ID | 说明 |
|------|--------|------|
| 课程管理 | `courses` | 文件上传、搜索、表格、已选列表 |
| 智能排课 | `scheduling` | 配置、控制、进度、结果 |
| 导入导出 | `export` | 导入/导出Excel |
| 系统设置 | `settings` | 学分要求配置 |

### 3.2 前端组件

| 组件 | 状态 | 说明 |
|------|------|------|
| Header | ✅ 完整 | 标题、版本显示 |
| Sidebar | ✅ 完整 | 4个导航标签 |
| CourseSearch | ✅ 完整 | 实时搜索 |
| CourseTable | ✅ 完整 | Ag-Grid表格 |
| TimeSlotEditor | ❌ **占位符** | 显示"时间段编辑功能开发中..." |
| ConfigPanel | ✅ 完整 | 排课配置 |
| ControlPanel | ✅ 完整 | 开始/取消/重置 |
| ProgressDisplay | ✅ 完整 | 进度条 |
| ResultPanel | ✅ 完整 | 结果展示 |
| CreditPanel | ✅ 完整 | 学分总览 |
| CreditSettings | ✅ 完整 | 学分设置 |

### 3.3 后端API

| 端点 | 方法 | 状态 |
|------|------|------|
| `/api/courses/load` | POST | ✅ |
| `/api/courses` | GET | ✅ |
| `/api/courses/search` | GET | ✅ |
| `/api/courses/{code}` | GET | ✅ |
| `/api/selected-courses` | GET | ✅ |
| `/api/selected-courses` | POST | ✅ |
| `/api/selected-courses/{id}` | DELETE | ✅ |
| `/api/selected-courses/{id}/timeslots` | POST | ✅ 已实现但前端未用 |
| `/api/selected-courses/{id}/category` | PUT | ✅ |
| `/api/scheduling/config` | GET/POST | ✅ |
| `/api/scheduling/execute` | POST | ✅ |
| `/api/scheduling/status` | GET | ✅ |
| `/api/scheduling/cancel` | POST | ✅ |
| `/api/credits` | GET | ✅ |
| `/api/credits/settings` | GET/POST | ✅ |
| `/api/export/selected-courses` | POST | ✅ |
| `/api/export/schedule-result` | POST | ✅ |
| `/api/import/selected-courses` | POST | ✅ |

---

## 四、功能差异对比矩阵

| 序号 | 功能 | Qt版本 | Web版本 | 差异等级 | 备注 |
|------|------|--------|---------|----------|------|
| 1 | 课程数据加载 | ✅ | ✅ | 无 | |
| 2 | 课程搜索 | ✅ | ✅ | 无 | |
| 3 | 添加课程 | ✅ | ✅ | 无 | |
| 4 | 移除课程 | ✅ | ✅ | 无 | |
| 5 | 清空所有 | ✅ | ❌ | 中等 | Web无此按钮 |
| 6 | 课程表格 | ✅ 10列 | ✅ 较少 | 轻微 | |
| 7 | **时间段配置** | ✅ 完整 | ❌ **占位符** | **严重** | App.tsx:328行 |
| 8 | 学分类别管理 | ✅ | ✅ | 无 | |
| 9 | 类别锁定 | ✅ | ❌ **API有UI无** | **严重** | DTO:is_category_locked未用 |
| 10 | 学分设置 | ✅ | ✅ | 无 | |
| 11 | 排课算法 | ✅ | ✅ | 无 | |
| 12 | 排课配置 | ✅ | ✅ | 无 | |
| 13 | **周课表显示** | ✅ 导出 | ❌ **无** | **严重** | import_export.py:301行 |
| 14 | 导出已选课程 | ✅ 3 Sheet | ✅ 1 Sheet | 中等 | |
| 15 | 导入已选课程 | ✅ | ✅ | 无 | |
| 16 | 导出排课结果 | ✅ | ✅ | 无 | |
| 17 | **课程补充测试** | ✅ 完整 | ❌ **无UI** | **严重** | 后端存在无界面 |
| 18 | 冲突显示 | ✅ 表格实时 | ⚠️ 仅结果 | 轻微 | |

---

## 五、代码验证记录

### 5.1 Web版本时间段配置占位符

**文件**：`web/src/App.tsx`  
**行号**：324-330

```tsx
{selectedCourse && (
  <div className="bg-white rounded-lg shadow p-6">
    <h3 className="text-lg font-medium text-gray-900 mb-4">时间段管理</h3>
    <p className="text-gray-500">课程: {selectedCourse.course.course_name}</p>
    <p className="text-sm text-gray-400 mt-2">时间段编辑功能开发中...</p>
  </div>
)}
```

**验证**：确认TimeSlotEditor组件已创建但未集成使用。

### 5.2 后端时间段API存在

**文件**：`web_backend/api/courses.py`  
**行号**：168-187

```python
@router.post("/selected-courses/{course_id}/timeslots", response_model=SelectedCourseDTO)
async def add_time_slot(course_id: str, time_slot: TimeSlotDTO):
    """为已选课程添加时间段"""
    # 实现代码存在
```

**验证**：后端API已完整实现，前端仅需集成调用。

### 5.3 类别锁定DTO定义

**文件**：`web_backend/models/dto.py`  
**行号**：70

```python
is_category_locked: bool = Field(False, description="类别是否锁定")
```

**文件**：`web_backend/api/courses.py`  
**行号**：61

```python
is_category_locked=False,  # 硬编码默认值
```

**验证**：DTO中定义了字段，但前端UI和后端API均未实现锁定功能。

### 5.4 Qt版本周课表导出

**文件**：`core/import_export.py`  
**行号**：300-350

```python
def _create_weekly_schedule_sheet(self, wb, selected_courses):
    """创建周课表工作表"""
    ws = wb.create_sheet("周课表")
    time_slots = [
        ("第1-2节\n08:00-09:40", 1, 2),
        ("第3-4节\n10:00-11:40", 3, 4),
        ("第5-6节\n13:00-14:40", 5, 6),
        ("第7-8节\n15:00-16:40", 7, 8),
        ("第9-10节\n18:00-19:40", 9, 10),
    ]
    headers = ["节次", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
```

**验证**：Qt版本有完整的周课表导出逻辑，Web版本无对应功能。

---

## 六、增强实现计划

### 6.1 阶段一：关键功能实现（P0）

#### 任务1：时间段配置功能

**优先级**：P0 - 严重缺失  
**预计工作量**：3-4小时

**文件修改清单**：

1. `web/src/components/course/TimeSlotEditor.tsx`
   - 状态：组件已创建，需完善实现
   - 需要：集成到App.tsx使用

2. `web/src/App.tsx`
   - 行号：324-330
   - 修改：将占位符替换为TimeSlotEditor组件
   - 添加选中课程的时间段显示和编辑

3. `web/src/hooks/useApi.ts`
   - 需要：添加`updateTimeSlot` API调用函数

4. `web/src/api/client.ts`
   - 需要：添加时间段相关API调用

**实现要点**：

- 参考`ui/dialogs.py`的`TimeSlotDialog`实现
- 星期选择：周一至周日
- 节次选择：开始/结束（1-12）
- 周次选择：18个可点击按钮网格（参考Qt的20个，调整为18个）
- 全选/清空快捷操作
- API调用：`POST /api/selected-courses/{id}/timeslots`
- 删除时间段：`DELETE /api/selected-courses/{id}/timeslots/{slot_id}`

**验收标准**：

- [ ] 用户点击已选课程可打开时间段编辑
- [ ] 可添加/删除时间段
- [ ] 周次选择有视觉反馈
- [ ] 保存后刷新显示

---

#### 任务2：周课表可视化显示

**优先级**：P0 - 严重缺失  
**预计工作量**：4-5小时

**文件修改清单**：

1. 新增 `web/src/components/schedule/WeeklySchedule.tsx`
   - 5行×7列网格（上午/下午/晚上 × 周一至周日）
   - 每格显示课程名称
   - 点击可查看详情

2. `web/src/App.tsx` 或 `Sidebar.tsx`
   - 添加"课表查看"入口（可作为Tab或Modal）

3. `web_backend/api/schedule.py`（新建）
   - `GET /api/schedule/weekly` - 获取周课表数据

**实现要点**：

- 参考`core/import_export.py`的`_create_weekly_schedule_sheet`逻辑
- 时间段定义：
  - 第1-2节 08:00-09:40
  - 第3-4节 10:00-11:40
  - 第5-6节 13:00-14:40
  - 第7-8节 15:00-16:40
  - 第9-10节 18:00-19:40
- 支持两种视图：已选课程视图、排课结果视图
- 课程信息：名称、教师、校区、周次

**验收标准**：

- [ ] 可视化显示周一至周五的课程安排
- [ ] 支持已选课程和排课结果两种视图
- [ ] 点击课程格显示详细信息

---

#### 任务3：课程补充测试UI

**优先级**：P0 - 严重缺失  
**预计工作量**：4-5小时

**文件修改清单**：

1. 新增 `web/src/components/tools/CourseSupplement.tsx`
   - 文件上传：排课结果.xlsx
   - 文件上传：备选课程表.xlsx
   - "开始测试"按钮
   - 结果展示区域

2. `web/src/App.tsx` 或新建Tab
   - 添加"课程补充测试"入口

3. `web_backend/api/tools.py`（新建）
   - `POST /api/tools/supplement` - 执行补充测试

**实现要点**：

- 参考`scripts/course_supplement_test.py`逻辑
- 功能流程：
  1. 用户上传排课结果Excel
  2. 用户上传备选课程表Excel
  3. 后端识别遗漏课程
  4. 后端基于约束尝试添加
  5. 返回结果：成功添加的课程、失败的课程及原因
- 结果展示：
  - 成功列表
  - 失败原因分类（时间冲突、校区冲突、其他）
  - 统计：成功率

**验收标准**：

- [ ] 可上传两个Excel文件
- [ ] 显示识别出的遗漏课程
- [ ] 可执行补充测试
- [ ] 显示测试结果统计

---

#### 任务4：类别锁定功能

**优先级**：P0 - 严重缺失  
**预计工作量**：2-3小时

**文件修改清单**：

1. `web/src/components/course/CourseTable.tsx`
   - 添加锁定列（图标Toggle）
   - 行内显示锁定状态
   - 点击切换锁定

2. `web/src/App.tsx`
   - 实现`onUpdateCategory`函数
   - 传递到CourseTable

3. `web_backend/api/courses.py`
   - 添加 `PUT /api/selected-courses/{id}/lock`
   - 修改 `is_category_locked` 更新逻辑

**实现要点**：

- DTO已有`is_category_locked`字段（`web_backend/models/dto.py:70`）
- 前端显示锁定图标（Lucide React的Lock/Unlock）
- 锁定后该行类别不可编辑
- API调用更新锁定状态

**验收标准**：

- [ ] 表格显示锁定列
- [ ] 可点击切换锁定状态
- [ ] 锁定后类别不可编辑

---

### 6.2 阶段二：功能完善（P1）

#### 任务5：清空所有已选课程

**优先级**：P1 - 中等缺失  
**预计工作量**：1小时

**文件修改**：

1. `web/src/App.tsx` - 课程管理页面
   - 添加"清空所有"按钮

2. `web_backend/api/courses.py`
   - 添加 `DELETE /api/selected-courses/all`

**验收标准**：

- [ ] 点击清空所有可移除全部已选课程

---

#### 任务6：完善课程表格信息

**优先级**：P1 - 中等缺失  
**预计工作量**：2小时

**文件修改**：

1. `web/src/components/course/CourseTable.tsx`
   - 增加显示列（对比Qt的10列）
   - 调整Ag-Grid列配置

**验收标准**：

- [ ] 表格显示更多信息（原始类别、时间安排等）

---

#### 任务7：增强导出功能

**优先级**：P1 - 中等缺失  
**预计工作量**：2-3小时

**文件修改**：

1. `web_backend/api/export.py`
   - 修改导出逻辑，生成多Sheet
   - 添加统计信息Sheet

**验收标准**：

- [ ] 导出包含多个Sheet
- [ ] 包含统计信息

---

### 6.3 阶段三：优化增强（P2）

| 任务 | 描述 | 预计工作量 |
|------|------|-----------|
| 冲突实时检测 | 选择课程时即时检测冲突 | 2小时 |
| PDF导出 | 生成PDF格式课表 | 3小时 |
| 历史记录 | 保存排课历史 | 3小时 |
| 批量操作 | 批量添加/移除课程 | 2小时 |

---

## 七、技术实现详细说明

### 7.1 后端API需求清单

```
现有API（无需修改）：
✅ POST /api/courses/load
✅ GET  /api/courses
✅ GET  /api/courses/search
✅ GET  /api/selected-courses
✅ POST /api/selected-courses
✅ DELETE /api/selected-courses/{id}
✅ POST /api/selected-courses/{id}/timeslots  ← 前端需集成
✅ PUT  /api/selected-courses/{id}/category
✅ GET  /api/scheduling/config
✅ POST /api/scheduling/config
✅ POST /api/scheduling/execute
✅ GET  /api/credits
✅ POST /api/credits/settings
✅ POST /api/export/selected-courses
✅ POST /api/export/schedule-result
✅ POST /api/import/selected-courses

需新增API：
❌ DELETE /api/selected-courses/all          ← 任务5
❌ PUT  /api/selected-courses/{id}/lock      ← 任务4
❌ GET  /api/schedule/weekly                ← 任务2
❌ POST /api/tools/supplement                ← 任务3
❌ DELETE /api/selected-courses/{id}/timeslots/{slot_id}  ← 任务1
```

### 7.2 前端组件结构

```
web/src/
├── components/
│   ├── course/
│   │   ├── CourseSearch.tsx      ✅
│   │   ├── CourseTable.tsx      ⚠️ 需添加锁定列
│   │   └── TimeSlotEditor.tsx   ⚠️ 需集成
│   ├── schedule/
│   │   └── WeeklySchedule.tsx   ❌ 需新建（任务2）
│   ├── tools/
│   │   └── CourseSupplement.tsx ❌ 需新建（任务3）
│   └── ...
├── api/
│   └── client.ts                ⚠️ 需添加API调用
└── hooks/
    └── useApi.ts                ⚠️ 需添加API调用
```

### 7.3 数据模型对应

**现有TypeScript类型**（`web/src/types/models.ts`）：

```typescript
interface SelectedCourse {
  id: string;
  course: Course;
  class_index: number;
  custom_category: string;
  is_category_locked: boolean;  // ← 需使用
  time_slots: TimeSlot[];
}

interface TimeSlot {
  day_of_week: number;
  start_period: number;
  end_period: number;
  weeks: number[];
}
```

---

## 八、工作量估算汇总

| 阶段 | 任务 | 预计工作量 | 累计 |
|------|------|-----------|------|
| **阶段一** | 任务1：时间段配置 | 3-4小时 | 3-4小时 |
| **阶段一** | 任务2：周课表显示 | 4-5小时 | 7-9小时 |
| **阶段一** | 任务3：课程补充测试 | 4-5小时 | 11-14小时 |
| **阶段一** | 任务4：类别锁定 | 2-3小时 | 13-17小时 |
| **阶段二** | 任务5：清空所有 | 1小时 | 18小时 |
| **阶段二** | 任务6：完善课程表格 | 2小时 | 20小时 |
| **阶段二** | 任务7：增强导出 | 2-3小时 | 22-25小时 |
| **阶段三** | 优化功能 | 约10小时 | 约35小时 |

**总预计工作量**：约25-35小时（不含阶段三）

---

## 九、风险与注意事项

### 9.1 技术风险

1. **时间段编辑并发**：多用户同时编辑需考虑锁机制
2. **大文件处理**：Excel导出大量课程时需考虑性能
3. **WebSocket状态**：排课执行的实时状态推送需确保连接稳定

### 9.2 兼容性问题

1. **浏览器兼容性**：确保新增组件在各浏览器正常显示
2. **移动端适配**：周课表在小屏幕设备上的显示效果

### 9.3 测试建议

1. 每个任务完成后进行单元测试
2. 重点测试：时间段CRUD、导出Excel格式、周课表渲染
3. 回归测试：确保不破坏现有功能

---

## 十、结论

经过深入分析，Web版本相比Qt版本存在以下关键差距：

1. **4项严重功能缺失**：时间段配置、周课表显示、课程补充测试、类别锁定
2. **3项中等功能简化**：清空全部、课程表格、导出格式

建议按照本计划分阶段实现，优先完成P0级别任务，确保核心功能与Qt版本持平。

---

**文档结束**

*本文档基于2026年2月14日的代码分析，后续可能因代码变更而需更新。*
