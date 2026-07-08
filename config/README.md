# config/ - 运行配置

进入 `config/` 前先读本文件。本目录负责数据源、报告提示词、目标品牌和大模型配置。

## 文件说明

- `settings.yaml`：主运行配置，包含懂车帝 API、请求控制、补充抓取 URL/选择器、MarkItDown 选项和通用 LLM 兜底配置。
- `brands.json`：抓取脚本使用的品牌关注清单和品牌 ID。
- `report_prompt.txt`：旧版 `tools/report_generator.py` 使用的日报提示词。
- `workflow_prompt.md`：工作流主控/意图解析 LLM 的系统提示词，支持 `action=run|ask|refuse`、`clarifying_question`、`workflow_notes` 和 `risk_notes`。
- `report_agent_prompt.md`：动态日报正文 LLM 的系统提示词。
- `agent_prompt.md`：动态日报正文提示词的旧兼容回退文件。
- `supplement_params.json`：旧补充参数实验使用的映射/配置。
- `README.md`：本目录索引。

## LLM 配置

不要提交真实 API Key。

推荐使用分离后的两套运行配置：

```powershell
$env:WORKFLOW_LLM_API_KEY="..."
$env:WORKFLOW_LLM_API_BASE="https://open.bigmodel.cn/api/paas/v4"
$env:WORKFLOW_LLM_MODEL="glm-4-flash"
$env:REPORT_LLM_API_KEY="..."
$env:REPORT_LLM_API_BASE="https://open.bigmodel.cn/api/paas/v4"
$env:REPORT_LLM_MODEL="glm-4-flash"
```

后端也会读取仓库根目录 `.env.local`：

```text
WORKFLOW_LLM_API_KEY=...
WORKFLOW_LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
WORKFLOW_LLM_MODEL=glm-4-flash
REPORT_LLM_API_KEY=...
REPORT_LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
REPORT_LLM_MODEL=glm-4-flash
```

也可以使用 `config/local.yaml`：

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

旧的 `LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL` 仍作为两套 profile 的兜底配置。网页工作台不显示 API Key 输入框，凭据应由本地后端通过环境变量或私有本地配置提供。使用 `/api/llm/status` 检查 `workflow` 和 `report` 两套配置状态。

## Agent 路由

- 抓取端点或选择器失效时，检查 `settings.yaml`。
- 品牌缺失或跳过时，检查 `brands.json` 和 `tools/fetch_brand_ids.py`。
- 旧版 LLM 日报措辞错误时，检查 `report_prompt.txt`。
- 工作流任务解析、追问或拒绝逻辑错误时，检查 `workflow_prompt.md` 和 `tools/intent_parser.py`。
- 动态网页报告写作要求错误时，检查 `report_agent_prompt.md` 和 `tools/dynamic_report_generator.py`。
- 动态网页报告内容错误时，从 `tools/dynamic_report_generator.py` 开始排查；它只使用选定的配置值进行 LLM 调用。

## 安全

- 不要把密钥放入本目录并提交；使用环境变量或已忽略的本地覆盖文件。
- 不要硬编码本地私密路径。
- YAML、JSON 和提示词文件保持 UTF-8 编码。

## 维护说明

- 修改配置前，先在根目录 `progress.md` 记录任务上下文；完成后记录改动、验证命令和剩余风险。
- 工作流解析规则变化时，同步更新 `workflow_prompt.md`。
- 仓库规则、数据可信度约束或报告写作要求变化时，同步更新 `report_agent_prompt.md`。
- 配置文件或运行输入变化时，同步更新本文件、根 `AGENTS.md` 和根 `README.md`。
