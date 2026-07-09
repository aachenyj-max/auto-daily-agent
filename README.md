# 汽车车型及报价日报 Agent

自动抓取目标汽车网站最新车型与报价信息，生成每日日报并给出购买建议。

## 项目结构

```
日报agent/
├── skills/          # WorkBuddy Skill 定义
│   ├── web-scraper/         # HTML 页面抓取（CSS 选择器、结构化数据）
│   ├── markitdown-skill/    # 多格式 → Markdown 清洗转换
│   └── README.md
├── tools/           # 脚本与工具（抓取、清洗、生成等）
│   ├── scraper.py           # API 抓取脚本（主动用）
│   ├── scraper_simple.py    # API 抓取（简化版）
│   ├── enrich.py            # 补充管线（web-scraper + markitdown）
│   ├── processor.py         # 数据清洗与结构化
│   ├── report_generator.py  # LLM 日报生成
│   └── validate.py          # 数据校验
├── data/            # 抓取的数据
│   ├── raw/         #   原始数据（按日期归档）
│   └── processed/   #   清洗后的结构化数据（按日期归档）
├── output/          # 每日最终日报输出
├── frontend/        # 本地日报查看器
│   ├── index.html
│   └── src/
├── docs/            # 规划与说明文档
├── config/          # 配置文件（目标网站、品牌清单、模板等）
├── logs/            # 运行日志
├── progress.md      # 当前进度与后续任务
└── README.md        # 本文件
```

## 工作流程

项目包含两条互补的数据管线：

### 主管线：API 抓取（快速结构化数据）

```
懂车帝 JSON API
     ↓  [tools/scraper.py]
data/raw/YYYY-MM-DD.json     ← 价格 / 销量 / 排名
     ↓  [tools/processor.py]
data/processed/YYYY-MM-DD.json
     ↓  [tools/report_generator.py]
output/YYYY-MM-DD.md          ← 日报 + 购买建议
```

### 补充管线：HTML 抓取 + 清洗（富文本详情）

```
懂车帝 HTML 页面（参数页 / 评测文 / 口碑）
     ↓  [skills/web-scraper]     ← CSS 选择器提取 HTML 内容
原始 HTML 片段 / JSON
     ↓  [skills/markitdown-skill] ← HTML → Markdown 清洗
干净 Markdown 文本
     ↓  [tools/enrich.py]         ← 结构化组织
data/enriched/                    ← 补充数据
     ↓  [tools/report_generator.py]  ← 汇入 LLM 上下文
output/YYYY-MM-DD.md              ← 内容更丰富的日报
```

### 摘要

| 管线 | 工具 | 数据来源 | 产出 | 特点 |
|------|------|---------|------|------|
| **主** | scraper.py → processor.py | 懂车帝 JSON API | 价格/销量/排名的结构化数据 | 快、稳定、自动 |
| **辅** | web-scraper → markitdown → enrich.py | 懂车帝 HTML 页面 | 车型参数/评测/口碑等富文本 | 信息深度更高 |

### 执行步骤

```bash
# 1. 抓取基础数据（API）
python tools/scraper.py

# 2. 清洗数据
python tools/processor.py

# 3. (可选) 补充抓取详情页丰富数据
python tools/enrich.py

# 4. 生成日报
python tools/report_generator.py

# 5. 校验指定日期产物
python tools/validate.py --date 2026-07-03
```

## 本地查看器

项目包含一个轻量前端，用于在本地浏览器查看 `output/YYYY-MM-DD.md` 日报。

```bash
python tools/serve_frontend.py
```

启动后访问：

```
http://127.0.0.1:8000/frontend/index.html
```

当前前端支持日期选择、今天、前一天、后一天、重新加载、清除搜索、打开日报文件、最近查看记录、关键词搜索和 Markdown 渲染。前端只读取日报产物，不修改 `output/`、`data/` 或 `config/`。

也可以直接双击 `start_viewer.cmd`，它会在本地启动只读查看器并自动打开浏览器。

## 配置

- `config/settings.yaml` — API 配置、请求控制、LLM 配置、web_scraper 抓取目标
- `config/brands.json` — 目标品牌清单
- `config/report_prompt.txt` — 日报生成 Prompt 模板

## 文档

- `docs/frontend-local-viewer.md` — 本地查看器规划与边界
- `progress.md` — 当前进度和后续任务
- `docs/runtime-task-log.md` — 工作台和后台 agent 运行记录

## Agent 协作与进度记录

每次开发任务都要把过程记录到 `progress.md`：开始时记录目标、上下文、计划和待办，完成时记录已改内容、验证命令、产物路径和剩余风险。这样即使任务中断，下一次接手也能从 `progress.md` 继续。

工作台或后台 agent 的运行结果不要继续堆到 `progress.md`。这类 `run/ask/refuse`、输出文件、质量状态和风险提示统一记录到 `docs/runtime-task-log.md`。

每次运行或接手任务时，先阅读 `AGENTS.md`、本文件和 `progress.md`。进入 `tools/`、`skills/`、`config/`、`data/`、`output/`、`frontend/` 或 `docs/` 前，再阅读该目录的 `README.md`，按索引打开必要文件，避免反复扫描大目录浪费 token。

每次修改代码、配置、数据约定、入口脚本或目录职责时，都要同步检查并按需更新 `AGENTS.md`、根 `README.md`、`progress.md` 和受影响一级目录的 `README.md`。若仓库规则、数据可信度约束或报告写作要求变化，还要同步更新 `config/agent_prompt.md`。

## 目录 README 索引

各一级目录的 `README.md` 是给人和大模型 agent 使用的快速地图。处理某个目录前，优先阅读对应 README，避免直接扫描全部文件：

- `tools/README.md` — 脚本入口、工作流、动态生成和 enriched 校验说明
- `skills/README.md` — 本地技能用途和读取路由
- `config/README.md` — 配置文件、LLM 设置和安全约束
- `data/README.md` — raw/processed/enriched 数据角色和可信度提示
- `output/README.md` — 报告命名、生产者和消费者
- `frontend/README.md` — 本地工作台文件、API 合约和验证命令
- `docs/README.md` — 规划文档索引
# 新版本地工作台入口

网页生成输入框需要启动工作流服务：

```powershell
python tools\workflow_server.py
```

也可以直接双击 `start_workbench.cmd`，它会在本地启动工作台服务并自动打开浏览器。

如果你更希望用一个稳定、可见日志的双击入口，直接运行：

```powershell
run_workbench.bat
```

它会打开一个名为 `Auto Daily Workbench Server` 的命令行窗口来常驻运行后端，再自动打开工作台页面。页面关闭后，服务窗口仍会保留；不需要时直接关掉该窗口即可。

如果你的机器对“新开窗口再拉起 Python”这条链路仍不稳定，就直接双击：

```powershell
run_workbench_server.bat
```

这个版本最直接：在当前命令行窗口里前台运行 `workflow_server.py`，同时打开工作台网址。使用期间不要关闭这个黑窗口；关闭它就等于停止本地服务。

如果你不想每次手动重启服务，可以运行一次：

```powershell
install_workbench_autostart.cmd
```

它会把 `start_workbench_background.cmd` 注册到 Windows 启动目录。之后每次登录系统都会静默检查并拉起工作台后端，但不会主动打开浏览器；你只需要访问 `http://127.0.0.1:8000/frontend/`。如需取消，运行 `remove_workbench_autostart.cmd`。

启动后访问：

```text
http://127.0.0.1:8000/frontend/
```

前端可以输入自然语言任务，例如“生成今天小鹏汽车日报，重点分析小鹏MONA M03”或“生成20万以内SUV购买建议”。后端只执行白名单工作流：解析需求、确认当天数据、抓取/清洗/补充缺失数据、生成 Markdown、校验产物。API Key 不在页面显示或传输，应由本地后端通过环境变量或私有本地配置提供。

工作台的主输入区是对话式任务入口：没有选中报告时会创建新报告任务，选中左侧报告后会基于当前报告继续交流。如果 Agent 需要确认车型或其他条件，追问会显示在同一对话流里，继续在同一个输入框回答即可。

生成任务默认启用大模型路径。工作流分为两套 LLM profile：`workflow` 负责解析自然语言任务，系统提示词为 `config/workflow_prompt.md`；`report` 负责生成报告正文，系统提示词为 `config/report_agent_prompt.md`。若某一路 LLM 配置缺失或调用失败，会自动回退到规则模板或规则解析。

本地后端支持以下私有配置方式，均已被 `.gitignore` 忽略：

```powershell
$env:WORKFLOW_LLM_API_KEY="..."
$env:WORKFLOW_LLM_API_BASE="https://open.bigmodel.cn/api/paas/v4"
$env:WORKFLOW_LLM_MODEL="glm-4-flash"
$env:REPORT_LLM_API_KEY="..."
$env:REPORT_LLM_API_BASE="https://open.bigmodel.cn/api/paas/v4"
$env:REPORT_LLM_MODEL="glm-4-flash"
```

也可在仓库根目录创建 `.env.local`：

```text
WORKFLOW_LLM_API_KEY=...
WORKFLOW_LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
WORKFLOW_LLM_MODEL=glm-4-flash
REPORT_LLM_API_KEY=...
REPORT_LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
REPORT_LLM_MODEL=glm-4-flash
```

或创建 `config/local.yaml`：

```yaml
llm:
  workflow:
    api_key: "..."
    api_base: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4-flash"
  report:
    api_key: "..."
    api_base: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4-flash"
```

前端会请求 `/api/llm/status` 显示 `workflow` 和 `report` 两套大模型是否已配置，并在任务完成时显示本次是否真正使用了正文大模型或回退原因。工作流任务支持 `action=run|ask|refuse`：`ask` 会返回 `needs_input` 并展示追问，`refuse` 会返回 `refused` 并展示安全原因；job 结果中的 `workflow_notes` 和 `risk_notes` 用于解释默认策略、风险和降级。

动态生成器会读取 `data/processed/enriched/YYYY-MM-DD.json` 的车型补充配置，但只有当参数正文通过车型名或版本名匹配校验时才会写入报告。未通过校验的配置会被跳过，避免把错配车型参数写进日报。

## 2026-07-06 安全说明

- 不要把 LLM API Key 写入 `config/settings.yaml` 后提交；请使用 `WORKFLOW_LLM_*`、`REPORT_LLM_*` 环境变量、`.env.local` 或 `config/local.yaml`。
- 网页不显示 API Key 输入框，也不保存或传输 API Key；请使用环境变量或私有本地配置。
- `tools/workflow_server.py` 只执行白名单工作流，不接受任意 Shell 命令。
- `data/cookies.json`、`data/session_info.json`、`.env` 和 `config/local.yaml` 已加入忽略规则。

## 2026-07-07 Backend Agent Stages

The workbench backend now uses a staged whitelist agent instead of a single opaque workflow hop.

- `tools/agent_runner.py` is the backend entry for workbench generation jobs.
- `tools/tool_registry.py` defines the only allowed tool chain:
  `read_context -> inspect_request -> inspect_data -> prepare_data -> build_context -> generate_report -> validate_report -> quality_check`
- `tools/workflow_runner.py` still owns the safe workflow primitives, but they are now exposed as explicit stages so the agent can execute and trace them separately.
- Job results may include `agent_trace` and `agent_task_context` for debugging and audit.

## 2026-07-08 Managed Report Layer

The workbench now includes a managed report layer on top of raw `output/*.md` files.

- Report metadata is indexed in `data/managed_reports/index.json`.
- `tools/report_registry.py` keeps that index in sync with `output/` and stores filter, archive, and follow-up metadata.
- The workbench API now supports:
  - `GET /api/reports/list`
  - `GET /api/reports/<report_id>`
  - `POST /api/reports/archive`
  - `POST /api/reports/restore`
  - `POST /api/reports/followup`
- Archive is soft only in the MVP. It changes metadata state and does not physically delete Markdown files.
- Follow-up generation is bound to a selected report and writes a new follow-up file instead of overwriting the source report.
