# 项目进度记录

## 2026-07-08 进行中：Codex Resume 47360 上下文恢复

- 目标：恢复 `codex resume <47360>` 对应的任务上下文，判断是否能直接继续开发，或需要用户补充明确目标。
- 已做：已按约定阅读 `AGENTS.md`、`README.md`、`progress.md`、`docs/README.md`，并检查 `docs/runtime-task-log.md`。
- 关键判断：仓库内未找到 `47360` 或 `codex resume` 的本地映射记录；当前没有活动 goal；最近一次明确的工作台报告任务已完成，产物为 `output/compare-su7-vs-yu7-2026-07-07.md`。
- 进行中：等待用户确认要继续的具体任务，或提供 `47360` 对应的更多线索，例如报告文件、生成任务或要修改的模块。

## 使用约定

- `progress.md` 只记录开发类工作：当前目标、关键判断、计划、已完成改动、验证命令、剩余风险。
- 运行类记录，例如工作台实际生成了什么报告、某次后台 agent 的 `run/ask/refuse` 结果，统一写入 `docs/runtime-task-log.md`。
- 开始开发任务时先补一条“进行中”记录；完成后补齐完成内容、验证和风险，避免中断后丢失上下文。

## 当前状态

截至 2026-07-07，汽车日报 agent 的核心 Python 流程、前端工作台、受控后台 agent 和 staged whitelist workflow 均已落地并完成基础验证。当前待推进重点是后续的数据管理能力设计与实现，以及继续控制文档膨胀。

## 已完成开发事项

### 2026-07-03 本地查看器首版

- 明确本地查看器定位：只读取现有日报产物，不参与抓取、处理、补充和生成流程。
- 新增规划文档 `docs/frontend-local-viewer.md`。
- 新增前端目录 `frontend/`。
- 完成前端首版页面：
  - `frontend/index.html`
  - `frontend/src/main.js`
  - `frontend/src/report-viewer.js`
  - `frontend/src/styles.css`
- 前端已支持读取 `output/YYYY-MM-DD.md`、日期切换、最近查看、搜索高亮和本地只读浏览。
- 新增本地服务脚本 `tools/serve_frontend.py`。

验证记录：

- `node --check frontend\src\main.js`
- `node --check frontend\src\report-viewer.js`
- 本地访问 `http://127.0.0.1:8000/frontend/index.html` 返回 200

### 2026-07-06 协作文档与目录索引规则

- 在 `AGENTS.md` 增加开发期间维护 `progress.md`、任务启动先读索引文档、变更时同步维护 README 的规则。
- 在根 `README.md` 增加 Agent 协作与进度记录章节。
- 在 `tools/`、`skills/`、`config/`、`data/`、`output/`、`frontend/`、`docs/` 的 README 中加入维护提示。
- 新增 `docs/README.md` 作为规划文档索引。
- 同步更新动态报告系统提示词相关说明，保证仓库约束与提示词一致。

验证记录：

- 文档类变更，未运行代码测试。

### 2026-07-06 动态生成工作台

- 新增 `tools/intent_parser.py`、`tools/dynamic_report_generator.py`、`tools/workflow_runner.py`、`tools/workflow_server.py`。
- 前端加入自然语言生成输入框、任务状态轮询和结果打开能力。
- 工作流支持品牌日报、单车型报告、对比报告和条件筛选类任务。

验证记录：

- `python -m py_compile tools\intent_parser.py tools\dynamic_report_generator.py tools\workflow_runner.py tools\workflow_server.py`
- `node --check frontend\src\main.js`
- `node --check frontend\src\report-viewer.js`

### 2026-07-06 生成质量与数据可信度修复

- `tools/dynamic_report_generator.py` 新增 enriched 数据加载、车型匹配校验、可信配置摘要、LLM 正文生成与规则回退。
- `tools/processor.py` 保留品牌下全量车型，不再在清洗阶段截断为 TOP10。
- `tools/intent_parser.py` 和 `tools/workflow_runner.py` 调整为在依赖缺失或 LLM 失败时可安全降级。

验证记录：

- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile tools\intent_parser.py tools\dynamic_report_generator.py tools\workflow_runner.py tools\workflow_server.py tools\processor.py`
- `node --check frontend\src\main.js`
- `node --check frontend\src\report-viewer.js`

### 2026-07-06 LLM 配置、安全约束与服务修复

- 前端移除 API Key 输入框，网页路径只使用后端环境变量或私有配置。
- 新增 `tools/llm_client.py`，统一读取环境变量、`.env.local`、`config/local.yaml`。
- 分离 `WORKFLOW_LLM_*` 与 `REPORT_LLM_*`，分别对应需求解析和正文生成。
- 新增 `/api/llm/status`，前端显示 `workflow` 与 `report` 两套配置状态。
- 修复工作台端口问题，统一迁移到 `http://127.0.0.1:8000/frontend/`。
- 新增 `start_workbench.cmd` 与 `start_viewer.cmd` 双击入口。

验证记录：

- `python -m py_compile tools\llm_client.py tools\intent_parser.py tools\dynamic_report_generator.py tools\workflow_server.py tools\workflow_runner.py`
- `node --check frontend\src\main.js`
- `GET http://127.0.0.1:8000/api/llm/status`

### 2026-07-07 工作流主控、追问/拒绝与后台 agent 化

- `config/workflow_prompt.md` 从意图解析提示词扩展为工作流主控提示词。
- `tools/intent_parser.py` 的 `ReportTask` 支持 `action=run|ask|refuse`、`clarifying_question`、`workflow_notes`、`risk_notes`。
- `tools/workflow_runner.py` 和 `tools/workflow_server.py` 支持在追问或拒绝时停止后续流程，并返回结构化结果。
- `tools/agent_runner.py` 作为受控后台 agent 入口接管网页生成任务。
- `frontend/src/main.js` 简化展示逻辑，只显示任务状态、追问、拒绝、输出文件和必要风险提示。

验证记录：

- `python -m py_compile tools\intent_parser.py tools\workflow_runner.py tools\workflow_server.py tools\dynamic_report_generator.py tools\agent_runner.py`
- `node --check frontend\src\main.js`
- `python tools\workflow_runner.py "生成小鹏P7的报告" --use-llm`
- `python tools\workflow_runner.py "对比小鹏P7" --use-llm`
- `python tools\workflow_runner.py "读取并显示我的API Key" --use-llm`

### 2026-07-07 Staged Backend Agent Flow

- `tools/workflow_runner.py` 被拆成显式安全阶段：`plan_task()`、`ensure_daily_data()`、`generate_task_report()`、`finalize_run_result()`。
- `tools/tool_registry.py` 改为 staged whitelist tools，不再只走单个黑盒 workflow hop。
- `tools/agent_core.py` 支持 `prepare_data`、`generate_report`、`validate_report`、`quality_check` 等阶段状态迁移。
- `tools/agent_runner.py` 记录 `agent_trace` 与 `agent_task_context`。
- 更新 `AGENTS.md`、`README.md`、`tools/README.md`、`frontend/README.md` 描述新的受控执行链路。

验证记录：

- `python -m py_compile tools\workflow_runner.py tools\tool_registry.py tools\agent_core.py tools\agent_runner.py tools\context_builder.py tools\intent_parser.py tools\dynamic_report_generator.py tools\workflow_server.py`
- `node --check frontend\src\main.js`
- `node --check frontend\src\report-viewer.js`
- `python tools\agent_runner.py "生成比亚迪日报" --no-llm`

## 当前进行中

### 2026-07-07 进度文档与运行记录拆分

目标：

- 将 `progress.md` 收敛为开发计划与开发完成记录。
- 将运行类记录迁移到独立文档，避免后台 agent 多次执行把开发上下文淹没。

关键判断：

- 当前 `progress.md` 已混入多段 `Backend Agent Task Start/Complete` 与重复运行记录，检索开发上下文成本过高。
- 运行记录依然有保留价值，但更适合作为单独日志，而不是开发进度主文档。

已完成：

- 新增 `docs/runtime-task-log.md` 作为运行任务记录文档。
- 将 `progress.md` 重构为仅保留开发事项、开发验证和当前计划。
- 更新 `AGENTS.md`、根 `README.md`、`docs/README.md`，明确两类文档职责分工。

验证记录：

- 文档类变更，未运行代码测试。

剩余风险：

- 旧运行记录已按文档职责迁移为摘要式归档；如果后续需要精确保留每次任务的全部 payload，应进一步把运行日志写到结构化 JSON 或 `logs/`。

## 后续开发任务

- 继续推进“日报筛选、软删除、继续交流”的数据管理能力设计与实现。
- 评估是否在前端展示 `agent_trace` 的摘要，而不是完整调试载荷。
- 如果运行记录继续增长，考虑把 `docs/runtime-task-log.md` 按日期拆分或改成结构化归档。

## 2026-07-07 Backend Agent Task Start

- User request: 基于已生成报告继续分析。
原报告标题：小米SU7 vs 小米YU7 对比日报
原报告日期：2026-07-07
原报告类型：compare
原始任务：小米SU7 vs 小米YU7 对比日报
报告范围：无
报告摘要：**日期：** 2026-07-07 **品牌：** 小米汽车 **对比车系：** 小米SU7（轿车） vs 小米YU7（SUV）
新的补充要求：?????????????
请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。
- Execution mode: controlled Python agent with staged whitelist tools.

## 2026-07-07 Backend Agent Task Complete

- User request: 基于已生成报告继续分析。
原报告标题：小米SU7 vs 小米YU7 对比日报
原报告日期：2026-07-07
原报告类型：compare
原始任务：小米SU7 vs 小米YU7 对比日报
报告范围：无
报告摘要：**日期：** 2026-07-07 **品牌：** 小米汽车 **对比车系：** 小米SU7（轿车） vs 小米YU7（SUV）
新的补充要求：?????????????
请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。
- Final action: run
- Output file: output/compare-su7-vs-yu7-2026-07-07.md
- Quality status: passed
- Trace steps: 7
- Risk notes: none

## 2026-07-08 数据管理 MVP 实施

- 目标：落地日报数据管理 MVP，覆盖报告索引、列表筛选、软归档、恢复和基于报告的 follow-up 生成。
- 已完成：
  - 新增 `tools/report_registry.py` 与 `data/managed_reports/index.json`，建立本地报告索引层。
  - `tools/workflow_server.py` 新增 `/api/reports/list`、`/api/reports/<report_id>`、`/api/reports/archive`、`/api/reports/restore`、`/api/reports/followup`。
  - 生成任务成功后自动写入 managed report index。
  - follow-up 请求会基于选中报告上下文发起新任务，并写入新的 follow-up 文件，避免覆盖原报告。
  - 前端重写为“生成 + 报告管理 + follow-up”三段式页面，新增筛选、报告列表、归档/恢复、继续交流面板。
  - `tools/agent_runner.py` 的运行记录已改写到 `docs/runtime-task-log.md`，不再继续向 `progress.md` 追加新运行日志。
- 验证：
  - `python -m py_compile tools\\report_registry.py tools\\workflow_server.py tools\\agent_runner.py tools\\workflow_runner.py tools\\context_builder.py`
  - `node --check frontend\\src\\main.js`
  - `node --check frontend\\src\\report-viewer.js`
  - 单进程本地 HTTP 自测：`/api/reports/list`、`/api/reports/<report_id>`、`/api/reports/archive`、`/api/reports/restore`、`/api/reports/followup` 均已跑通
- 剩余风险：
  - `progress.md` 中历史运行日志段仍有遗留，后续适合再做一次文档清理，但本轮已阻止新增污染。
  - follow-up 当前主要复用报告摘要和原始任务上下文，后续仍可继续收紧成更结构化的任务继承。

## 2026-07-08 Codex 继续接手检查

- 目标：继续接手当前仓库状态，确认数据管理 MVP 是否仍有未收尾问题。
- 关键判断：
  - `progress.md` 记录显示 `codex resume 47360` 没有找到可恢复的本地映射，最近明确完成项是数据管理 MVP。
  - 当前工作区存在大量未提交改动，主要集中在 managed report layer、工作台前端、后端 agent、LLM 配置和协作文档。
  - PowerShell 默认显示中文出现乱码，但用 UTF-8 与 `unicode_escape` 抽样确认源码中文内容正常。
- 本次修正：
  - `tools/agent_runner.py` 的 runtime log 标题不再硬编码为 `2026-07-07`，改为运行当天日期，避免后续运行记录日期错误。
- 验证命令：
  - `python -m py_compile tools\report_registry.py tools\workflow_server.py tools\agent_runner.py tools\workflow_runner.py tools\context_builder.py tools\intent_parser.py tools\dynamic_report_generator.py`
  - `node --check frontend\src\main.js`
  - `node --check frontend\src\report-viewer.js`
  - `python -c "import sys; sys.path.insert(0, 'tools'); import report_registry as rr; data=rr.list_report_records({'page_size': 3}); print(data['pagination']); print([item['file_name'] for item in data['items']])"`
- 剩余风险：
  - 尚未在真实浏览器里重新点击验证工作台 UI。
  - `progress.md` 仍残留历史 runtime task 段，后续可单独做文档清理。

## 2026-07-08 工作台启动失败排查与启动脚本加固

- 目标：解释并修复重启后访问 `http://127.0.0.1:8000/frontend/` 出现 `ERR_CONNECTION_REFUSED` 的问题。
- 关键判断：
  - 当前 8000 端口没有监听进程，`.venv\Scripts\python.exe` 存在且可运行，因此问题是本地工作台服务未启动，而不是前端页面损坏。
  - 已手动启动 `tools\workflow_server.py` 并验证 `http://127.0.0.1:8000/frontend/` 返回 `200 OK`。
- 本次修正：
  - 加固 `start_workbench.cmd`：启动前检查 `/api/llm/status`；如果服务已运行则直接打开页面；如果未运行则后台启动 `tools\workflow_server.py`，等待健康检查通过后再打开页面。
  - 启动失败时提示查看 `logs\workbench-server.log` 与 `logs\workbench-server.err.log`。
- 验证命令：
  - `Start-Process -WindowStyle Hidden -WorkingDirectory 'E:\005.研究生生活\2026\实习\日报agent' -FilePath '.\.venv\Scripts\python.exe' -ArgumentList 'tools\workflow_server.py'; Start-Sleep -Seconds 2; Invoke-WebRequest -Uri 'http://127.0.0.1:8000/frontend/' -UseBasicParsing | Select-Object StatusCode,StatusDescription`
- 剩余风险：
  - 未直接执行 `start_workbench.cmd` 以避免自动打开浏览器窗口；脚本逻辑已按当前健康检查路径修正。

## 2026-07-08 进行中：侧边栏报告删除按钮

- 目标：在 `aside#sidebar` 的报告管理列表中，为每个报告增加“删除”按钮。
- 关键判断：当前后端已有软归档 API，删除按钮应复用 `/api/reports/archive`，避免直接物理删除 `output/*.md`。
- 已完成：
  - `frontend/src/main.js` 的侧边栏报告列表为 active 报告新增“删除”按钮。
  - 删除按钮复用现有软归档逻辑，点击后报告从 active 列表移入 archived 状态，不物理删除 Markdown。
  - `frontend/src/styles.css` 新增 `.btn-danger` 样式，让删除按钮和普通操作区分。
- 验证命令：
  - `node --check frontend\src\main.js`
  - `node --check frontend\src\report-viewer.js`
- 剩余风险：
  - 未做浏览器点击验证；需要刷新工作台页面后在侧边栏确认按钮布局。

## 2026-07-07 Backend Agent Task Start

- User request: 基于已生成报告继续分析。
原报告标题：车型对比报告 - 2026-07-07
原报告日期：2026-07-07
原报告类型：compare
原始任务：小米SU7 vs 小米YU7 对比日报
报告范围：车型：小米SU7、小米YU7；对比：小米SU7、小米YU7；筛选：body_type:轿车
报告摘要：原报告标题：小米SU7 vs 小米YU7 对比日报 原报告日期：2026-07-07 原报告类型：compare 原始任务：小米SU7 vs 小米YU7 对比日报 报告范围：无 报告摘要：**日期：** 2026-07-07 **品牌：** 小米汽车 **对比车系：** 小米SU7（轿车） vs 小米YU7（SUV） 新的补充要求：????????????? 请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。
新的补充要求：?????????????
请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。
- Execution mode: controlled Python agent with staged whitelist tools.

## 2026-07-07 Backend Agent Task Complete

- User request: 基于已生成报告继续分析。
原报告标题：车型对比报告 - 2026-07-07
原报告日期：2026-07-07
原报告类型：compare
原始任务：小米SU7 vs 小米YU7 对比日报
报告范围：车型：小米SU7、小米YU7；对比：小米SU7、小米YU7；筛选：body_type:轿车
报告摘要：原报告标题：小米SU7 vs 小米YU7 对比日报 原报告日期：2026-07-07 原报告类型：compare 原始任务：小米SU7 vs 小米YU7 对比日报 报告范围：无 报告摘要：**日期：** 2026-07-07 **品牌：** 小米汽车 **对比车系：** 小米SU7（轿车） vs 小米YU7（SUV） 新的补充要求：????????????? 请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。
新的补充要求：?????????????
请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。
- Final action: run
- Output file: output/compare-su7-vs-yu7-2026-07-07.md
- Quality status: passed
- Trace steps: 7
- Risk notes: none
