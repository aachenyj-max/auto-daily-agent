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

## 配置

- `config/settings.yaml` — API 配置、请求控制、LLM 配置、web_scraper 抓取目标
- `config/brands.json` — 目标品牌清单
- `config/report_prompt.txt` — 日报生成 Prompt 模板

## 文档

- `docs/frontend-local-viewer.md` — 本地查看器规划与边界
- `progress.md` — 当前进度和后续任务
# 新版本地工作台入口

网页生成输入框需要启动工作流服务：

```powershell
python tools\workflow_server.py
```

启动后访问：

```text
http://127.0.0.1:8080/frontend/
```

前端可以输入自然语言任务，例如“生成今天小鹏汽车日报，重点分析小鹏MONA M03”或“生成20万以内SUV购买建议”。后端只执行白名单工作流：解析需求、确认当天数据、抓取/清洗/补充缺失数据、生成 Markdown、校验产物。API Key 可在页面临时输入，仅用于本次请求。

## 2026-07-06 安全说明

- 不要把 LLM API Key 写入 `config/settings.yaml` 后提交；请使用 `LLM_API_KEY` 环境变量、命令行 `--api-key`，或在网页中临时输入。
- 网页输入的 API Key 只随本次请求发送给本地后端，不写入前端存储。
- `tools/workflow_server.py` 只执行白名单工作流，不接受任意 Shell 命令。
- `data/cookies.json`、`data/session_info.json`、`.env` 和 `config/local.yaml` 已加入忽略规则。
