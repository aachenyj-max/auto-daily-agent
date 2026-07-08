# Repository Guidelines

## 项目结构与模块组织

本仓库是一个基于 Python 脚本的汽车日报 agent。核心流程位于 `tools/`：`scraper.py` 抓取 API 数据，`processor.py` 清洗并结构化数据，`enrich.py` 补充车型详情页信息，`report_generator.py` 生成日报，`validate.py` 校验产物。配置文件放在 `config/`，重点包括 `settings.yaml`、`brands.json` 和 `report_prompt.txt`。原始数据按日期保存到 `data/raw/`，处理后数据保存到 `data/processed/`，补充抓取的中间结果使用对应的 `enriched/` 子目录。最终日报输出到 `output/YYYY-MM-DD.md`。运行日志、调试页面和截图放在 `logs/`。本地可复用技能放在 `skills/`。本地前端查看器放在 `frontend/`，规划和进度文档放在 `docs/` 与 `progress.md`。

各一级目录的 `README.md` 是后续 agent 的快速索引。进入 `tools/`、`skills/`、`config/`、`data/`、`output/`、`frontend/` 或 `docs/` 前，应先阅读对应目录 README，再决定是否打开具体文件，避免无目的扫描大目录。

开发期间必须维护连续上下文：开始处理需求后，在 `progress.md` 记录当前目标、关键判断、进行中的步骤和待办；开发完成后，再记录完成内容、验证命令、产物路径和剩余风险，避免中断后下次 agent 不知道从何继续。`progress.md` 只用于开发计划和开发完成记录；工作台或后台 agent 的运行类记录应写入 `docs/runtime-task-log.md`，不要继续把大量 `Backend Agent Task Start/Complete` 一类内容追加到 `progress.md`。每次修改代码、配置、数据约定、入口脚本或目录职责时，都要同步检查并按需更新 `AGENTS.md`、根 `README.md`、`progress.md` 以及受影响一级目录的 `README.md`。每次运行或接手任务时，先阅读 `AGENTS.md`、根 `README.md`、`progress.md`，进入具体目录前再读该目录 `README.md`，不要直接全量扫描大目录浪费 token。

## 构建、测试与开发命令

在仓库根目录运行以下命令：

```powershell
python tools\scraper.py
python tools\processor.py
python tools\enrich.py
python tools\report_generator.py
python tools\validate.py --date 2026-07-03
python tools\serve_frontend.py
```

前四个命令对应常规流水线：抓取、处理、可选补充、生成日报。修改流程后，使用 `validate.py` 按日期检查原始数据、结构化数据和日报 Markdown 是否完整。`serve_frontend.py` 用于本地查看前端，不应改变任何日报产物。

## 编码风格与命名约定

Python 代码使用 4 空格缩进，优先复用标准库和现有脚本风格。路径处理应使用 `pathlib.Path`。日期产物统一命名为 `YYYY-MM-DD.json` 或 `YYYY-MM-DD.md`。新的流水线入口脚本放在 `tools/`，文件名使用清晰的动词短语，例如 `fetch_brand_ids.py`、`scrape_params.py`。前端源码放在 `frontend/`，首版保持原生 HTML/CSS/JS；若后续引入框架，仍应限制在 `frontend/` 内。JSON、Markdown、HTML、CSS 和 JS 文件读写应显式使用 UTF-8。

## 测试指南

当前仓库没有正式单元测试框架。提交流程相关改动前，至少运行：

```powershell
python tools\validate.py --date <YYYY-MM-DD>
```

如果修改了解析、清洗或生成逻辑，应先运行受影响的上游脚本，确保校验基于最新产物。只有在新增可复用函数或复杂转换逻辑时，再补充针对性的测试或夹具数据。

如果修改前端查看器，至少运行：

```powershell
node --check frontend\src\main.js
node --check frontend\src\report-viewer.js
python tools\serve_frontend.py
```

然后在浏览器访问本地页面，确认能加载 `output/YYYY-MM-DD.md`。

## 提交与拉取请求规范

当前工作目录没有 Git 历史，因此无法推断既有提交规范。提交信息建议使用简短的祈使句，例如 `Add enriched data validation` 或 `Fix report date handling`。Pull Request 应说明改动影响的流水线步骤、列出已运行命令、注明配置变更，并在日报内容变化时给出示例产物路径，例如 `output/2026-07-03.md`。

## 安全与配置提示

不要把 API Key、账号密码等敏感信息提交到配置文件。LLM 和网站凭据优先使用环境变量或本地覆盖配置。不要提交 `.venv/`、缓存文件或大型调试抓取结果，除非它们被明确作为测试夹具使用。

前端查看器默认只读 `output/` 和后续可能接入的 `data/processed/`。不要在前端代码中写入凭据、硬编码私密路径，或让静态页面直接承担流水线执行职责。

## 2026-07-06 工作台生成入口

本地网页现在支持自然语言生成任务。启动命令：

```powershell
python tools\workflow_server.py
```

访问地址：

```text
http://127.0.0.1:8000/frontend/
```

相关模块：
- `tools/intent_parser.py`：将自然语言需求解析成白名单报告任务。
- `tools/dynamic_report_generator.py`：根据结构化数据生成市场、品牌、车型、对比和筛选报告；勾选 LLM 时会优先使用 OpenAI 兼容接口生成正文，失败时回退规则模板。
- `tools/workflow_runner.py`：编排抓取、清洗、补充、生成和校验。
- `tools/workflow_server.py`：为前端提供本地 API 与 job 状态查询。
- `tools/agent_runner.py` / `tools/tool_registry.py` / `tools/agent_core.py`：受控后台 agent 主链路。只允许在注册表内按阶段执行 `read_context -> inspect_request -> inspect_data/prepare_data -> build_context -> generate_report -> validate_report -> quality_check`，并把执行轨迹写入 `agent_trace`。

安全约束：
- 不要把 API Key、Cookie、手机号、会话信息或本地私密路径提交到仓库。
- LLM Key 分为 `WORKFLOW_LLM_*` 和 `REPORT_LLM_*` 两套配置，优先使用环境变量或私有本地配置；前端不得显示、保存或传输 API Key。
- 私有本地配置可用仓库根目录 `.env.local` 或 `config/local.yaml`，二者必须保持忽略状态，不得提交真实 Key。
- 前端不得保存 API Key 到 `localStorage`，不得直接执行任意 Python/Shell。
- 后端只能执行白名单工作流，不接受任意命令或任意文件路径。
- `data/processed/enriched/YYYY-MM-DD.json` 中的车型配置必须通过车型名或版本名匹配校验后才可进入报告；未通过校验时只能提示“补充配置数据不可信/已跳过”。
- `processor.py` 应保留品牌下全量车型，报告层按需要限制展示数量，不要在清洗阶段截断为 TOP10。
- 修改一级目录职责、入口脚本或数据约定时，同步更新该目录的 `README.md`。
- 工作流解析大模型系统提示词位于 `config/workflow_prompt.md`；动态网页报告正文大模型系统提示词位于 `config/report_agent_prompt.md`。修改解析规则、仓库规则、数据可信度约束或报告写作要求时同步更新对应文件。
- 前端通过 `/api/llm/status` 展示 `workflow` 和 `report` 两套大模型配置状态。工作流任务支持 `action=run|ask|refuse`：`ask` 映射为 job 状态 `needs_input`，`refuse` 映射为 `refused`；job 结果中的 `workflow_notes`、`risk_notes`、`generation.llm_used` 和 `generation.llm_fallback_reason` 用于判断默认策略、风险降级和是否真实使用正文 LLM。
- 开发记录必须落到 `progress.md`：需求开始时记录计划和上下文，完成时记录改动、验证和未解决事项。
- 运行记录必须落到 `docs/runtime-task-log.md`：仅记录实际执行过的工作台/后台 agent 任务结果、输出文件、质量状态和简要风险。
- 后续每次任务启动时先读 `AGENTS.md`、`README.md`、`progress.md` 和目标目录 README，再决定打开哪些具体文件。
