# 项目进度记录

## 当前状态

截至 2026-07-03，汽车日报 agent 的核心 Python 流程已验证可用，前端本地查看器已完成首版 demo 并完成一次布局优化。

## 已完成任务

- 明确了本地查看器的定位：只读取现有日报产物，不参与抓取、处理、补充和生成日报流程。
- 新增规划文档：`docs/frontend-local-viewer.md`。
- 新增前端目录：`frontend/`。
- 完成前端首版页面：
  - `frontend/index.html`
  - `frontend/src/main.js`
  - `frontend/src/report-viewer.js`
  - `frontend/src/styles.css`
- 前端已支持读取 `output/YYYY-MM-DD.md` 并渲染 Markdown。
- 前端已支持日期选择、今天、前一天、后一天、重新加载、清除搜索、打开日报文件。
- 前端已支持最近查看记录，使用 `localStorage` 保存。
- 前端已支持关键词搜索和高亮。
- 前端已增加状态摘要条，展示日期、文件、字符数和加载状态。
- 前端布局已调整为本地工作台形式：顶部操作区、左侧最近查看、正文阅读区。
- 新增本地服务脚本：`tools/serve_frontend.py`。

## 已验证事项

- `node --check frontend\src\main.js` 通过。
- `node --check frontend\src\report-viewer.js` 通过。
- 本地静态访问 `http://127.0.0.1:8000/frontend/index.html` 返回 200。
- 前端文件编码确认使用 UTF-8。

## 当前边界

- 前端只读 `output/` 中的 Markdown 日报。
- 前端暂不直接执行 Python 流水线。
- 前端暂不修改 `data/`、`output/`、`config/` 中的任何产物。
- 结构化数据展示暂未接入。
- 校验、抓取、处理、补充、生成日报仍通过命令行运行。

## 后续任务

- 确认 `tools/serve_frontend.py` 的端口冲突处理是否满足日常使用。
- 增加可用日报列表，优先由本地服务扫描 `output/`。
- 增加 `data/processed/YYYY-MM-DD.json` 摘要视图。
- 增加品牌、车型、来源、线索类型等筛选能力。
- 增加“校验当前日期”入口，对应 `python tools\validate.py --date YYYY-MM-DD`。
- 增加日报与结构化数据之间的跳转定位。
- 增加简单统计图表。
- 根据实际使用反馈优化移动端布局。

## 文档维护

- `AGENTS.md` 已包含 `frontend/`、`docs/` 和本地查看器的边界说明。
- `README.md` 已包含本地查看器的目录说明和启动命令。
- 前端能力变化后，同步更新 `docs/frontend-local-viewer.md` 和本文件。

## 2026-07-06 动态生成输入框改造

目标：在网站界面加入自然语言生成输入框，支持“总览日报、单车企日报、单车型报告、车型对比、条件筛选购买建议”等需求。前端只提交任务和展示进度，后端通过白名单工作流执行抓取、清洗、补充、生成与校验。

任务进度：
- [x] 规划动态生成方案：输入框 + job 状态轮询 + 后端白名单工作流。
- [x] 新增任务意图解析模块 `tools/intent_parser.py`。
- [x] 新增动态报告生成模块 `tools/dynamic_report_generator.py`。
- [x] 新增工作流编排模块 `tools/workflow_runner.py`。
- [x] 新增本地 API 服务 `tools/workflow_server.py`。
- [x] 前端加入生成输入框、快捷示例、进度状态和结果打开能力。
- [x] 运行语法检查与最小工作流验证。

验证记录：
- `python -m py_compile tools\intent_parser.py tools\dynamic_report_generator.py tools\workflow_runner.py tools\workflow_server.py` 通过。
- `node --check frontend\src\main.js` 通过。
- `node --check frontend\src\report-viewer.js` 通过。
- `python tools\workflow_runner.py "生成今天小鹏汽车日报，重点分析小鹏MONA M03"` 通过，输出 `output/brand-xpeng-2026-07-06.md`。
- `tools\workflow_server.py` 本地 API 验证通过，生成接口可创建 job 并产出 Markdown。
