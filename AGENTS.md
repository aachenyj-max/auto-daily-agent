# Repository Guidelines

## 项目结构与模块组织

本仓库是一个基于 Python 脚本的汽车日报 agent。核心流程位于 `tools/`：`scraper.py` 抓取 API 数据，`processor.py` 清洗并结构化数据，`enrich.py` 补充车型详情页信息，`report_generator.py` 生成日报，`validate.py` 校验产物。配置文件放在 `config/`，重点包括 `settings.yaml`、`brands.json` 和 `report_prompt.txt`。原始数据按日期保存到 `data/raw/`，处理后数据保存到 `data/processed/`，补充抓取的中间结果使用对应的 `enriched/` 子目录。最终日报输出到 `output/YYYY-MM-DD.md`。运行日志、调试页面和截图放在 `logs/`。本地可复用技能放在 `skills/`。本地前端查看器放在 `frontend/`，规划和进度文档放在 `docs/` 与 `progress.md`。

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
http://127.0.0.1:8080/frontend/
```

相关模块：
- `tools/intent_parser.py`：将自然语言需求解析成白名单报告任务。
- `tools/dynamic_report_generator.py`：根据结构化数据生成市场、品牌、车型、对比和筛选报告。
- `tools/workflow_runner.py`：编排抓取、清洗、补充、生成和校验。
- `tools/workflow_server.py`：为前端提供本地 API 与 job 状态查询。

安全约束：
- 不要把 API Key、Cookie、手机号、会话信息或本地私密路径提交到仓库。
- LLM Key 优先使用 `LLM_API_KEY` 环境变量，或在网页临时输入，仅用于本次请求。
- 前端不得保存 API Key 到 `localStorage`，不得直接执行任意 Python/Shell。
- 后端只能执行白名单工作流，不接受任意命令或任意文件路径。
