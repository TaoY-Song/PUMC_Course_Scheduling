# PUMC 智能排班系统

PUMC 智能排班系统用于导入课程一览表、管理已选课程、设置学分要求、执行智能排课、导出排课结果，并支持补充测试。

本项目同时保留两个可用入口：

- Qt 桌面版：适合本地单机直接使用
- Web 版：适合浏览器工作流，界面更完整

## 你应该先用哪个版本

- 只想直接打开软件使用：用 Qt 版
- 想用浏览器界面、可视化课表：用 Web 版

## 环境要求

- Python 3.11
- Node.js 18 或更高版本
- Windows PowerShell 或 CMD

## 安装

### 1. 创建并激活 Python 虚拟环境（不建议安装在自己的本地环境）

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

CMD:

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. 安装 Web 前端依赖

```powershell
cd web
npm ci
cd ..
```

## 启动

### 启动 Qt 桌面版

```powershell
python app.py
```

可选参数：

```powershell
python app.py --log-level DEBUG
```

### 启动 Web 版

首次运行或前端有改动时，先构建前端：

```powershell
cd web
npm run build
cd ..
python app_web.py
```

默认访问地址：

- `http://127.0.0.1:8000`
- 接口文档：`http://127.0.0.1:8000/docs`

### Web 前端开发模式

如果你在改页面样式或交互，建议前后端分开运行：

后端：

```powershell
python app_web.py --dev --no-browser
```

前端：

```powershell
cd web
npm run dev
```

前端开发地址：

- `http://127.0.0.1:5173`

## 使用教程

下面是推荐的标准操作顺序。无论你使用 Qt 版还是 Web 版，核心流程都是一样的。

### 第一步：导入课程一览表

1. 打开课程工作台
2. 选择课程一览表 Excel 文件
3. 等待系统完成导入
4. 确认页面中已经出现课程列表和课程数量

说明：

- Web 版会缓存最近一次导入的课程源文件
- 补充测试默认会优先复用这份课程源文件

### 第二步：整理已选课程

在课程工作台中完成下面操作：

1. 搜索课程
2. 把需要的课程加入已选课程列表
3. 根据实际情况修改课程类别
4. 设置课程是否为线上课程
5. 如有必要，锁定课程类别
6. 为课程新增、修改或删除时间段

建议：

- 排课前先把时间段、线上状态和类别整理准确
- 如果课程很多，已选课程区域支持固定框滚动，不会再把页面撑乱

### 第三步：设置学分要求

默认值是**整个学位阶段**的培养方案总量。做单学期排课时，应填写本学期尚需完成的学分缺口；否则目标高于本学期课程供给时，优化模式可能合理地舍弃无法改善目标的课程。

进入“学分设置”页面后：

1. 查看当前各类别学分目标
2. 修改目标值
3. 点击保存
4. 返回课程页或排课页确认统计结果已经同步更新

### 第四步：执行智能排课

进入“智能排课”页面后：

1. 选择学分约束模式
2. 选择校区冲突模式
3. 设置时间限制、最大解数、学分溢出比例、校区转换时间
4. 先保存配置
5. 点击开始排课
6. 等待任务完成
7. 在结果区查看摘要、课程列表和周课表

说明：

- Web 版排课是异步任务，不会阻塞整个页面
- 页面会显示任务状态、进度消息和排课结果
- 当前取消为软取消，请求取消后系统会丢弃本次结果

### 第五步：导出排课结果

排课完成后，在“智能排课”页面直接点击导出按钮即可。

导出文件特点：

- 导出为 Excel
- 内容为逐条课程明细
- 不额外生成课表视图工作表
- 字段格式兼容补充测试脚本

### 第六步：运行补充测试

进入“补充测试”页面后：

1. 上传排课结果 Excel
2. 如有需要，再上传一份课程一览表作为覆盖课程源
3. 点击开始补充测试
4. 等待系统执行完成
5. 下载补充后的结果文件和日志文件

说明：

- 如果你没有手动上传课程一览表，系统会默认使用当前会话中最近导入的课程源文件
- 当前补充测试直接调用 `scripts/course_supplement_test.py`

## 常见问题（建议询问AI）

### 1. 依赖安装失败

优先在虚拟环境中执行：

```powershell
python -m pip install --upgrade pip setuptools
python -m pip install -r requirements.txt
```

如果是 Windows 临时目录问题，可以先手动指定：

```powershell
mkdir .tmp
$env:TEMP="$PWD\\.tmp"
$env:TMP="$PWD\\.tmp"
python -m pip install -r requirements.txt --no-cache-dir
```

### 2. 排课还需要 `ortools` 吗？

不需要。排课算法是纯 Python 的回溯搜索，`ortools` 已从依赖中移除。

历史上仓库里有一份基于 OR-Tools CP-SAT 的实现，但它没有任何调用方且并未完成
（时间约束、校区约束、每日上限的函数体是空的），同时在 Windows 上还会与 pandas
发生原生库冲突而报 `OSError: [WinError 127]`。这部分死代码已经删除。

如果你在旧环境里装过 `ortools`，保留或卸载都不影响本项目运行。

### 3. Web 页面打不开

先检查：

- `python app_web.py` 是否正常启动
- `web/dist` 是否已经生成
- 如果前端还没构建，先执行 `cd web` 和 `npm run build`

### 4. 补充测试提示没有课程源

说明当前会话里没有可用的课程一览表缓存。

解决方法：

1. 回到课程工作台重新导入一次课程一览表
2. 或者在补充测试页面手动上传课程一览表

## 常用命令

运行测试：

```powershell
python -m pytest
```

跳过较慢的求解器超时测试：

```powershell
python -m pytest -m "not slow"
```

前端检查：

```powershell
cd web
npm run type-check
npm run lint
npm run build
```

单独运行补充测试脚本：

```powershell
python scripts/course_supplement_test.py
```

## 日志

默认只输出 WARNING 及以上的日志。需要查看排课搜索过程时：

```powershell
# 方式一：命令行参数
python app.py --log-level DEBUG
python app_web.py --log-level DEBUG

# 方式二：环境变量
$env:PUMC_LOG_LEVEL="DEBUG"
```

Qt 版会同时把输出写入项目根目录的 `app.log`。

## License

本项目采用自定义非商用许可证。

- 允许非商业使用、学习、研究、修改和分发
- 禁止未经授权的商业使用
- 商业使用必须事先获得项目作者书面授权

完整条款见 [LICENSE](./LICENSE)。
