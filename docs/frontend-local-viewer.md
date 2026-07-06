# 本地日报查看器规划

## 定位

前端首版定位为本地日报查看器，用于在浏览器中查看已经生成的汽车日报和相关结构化数据。它只服务本地使用场景，不承担抓取、清洗、补充、生成日报等流水线职责。

## 运行边界

- 运行方式：本地浏览器访问。
- 数据来源：优先读取 `output/YYYY-MM-DD.md`，后续可读取 `data/processed/YYYY-MM-DD.json`。
- 写入行为：前端不修改 `output/`、`data/`、`config/` 或任何流水线产物。
- 使用场景：个人本地查看、日期切换、日报检索和后续结构化分析。
- 非目标：线上部署、权限系统、多人协作、远程 API、数据库存储。

## 建议目录

```text
frontend/
├─ index.html
├─ src/
│  ├─ main.js
│  ├─ report-viewer.js
│  └─ styles.css
└─ public/
```

如果后续引入 Vite、React 或其他前端框架，应继续将前端工程限制在 `frontend/` 目录内，不把页面组件、样式或构建产物散放到仓库根目录。

## 数据读取规则

首版以前端读取日报 Markdown 为主：

```text
output/YYYY-MM-DD.md
```

后续如果需要做品牌筛选、线索列表、数据统计或图表展示，再读取结构化数据：

```text
data/processed/YYYY-MM-DD.json
```

前端不复制日报数据，不生成新的业务数据文件。若浏览器安全限制导致无法直接读取本地文件，可以新增一个极简本地服务脚本，例如：

```text
tools/serve_frontend.py
```

该脚本只负责提供静态页面和只读数据访问，不参与日报流水线。

## 首版功能

- 选择日期并加载对应日报。
- 渲染 `output/YYYY-MM-DD.md` 的 Markdown 内容。
- 提供基础关键词搜索。
- 显示文件不存在、读取失败、空日报等状态。
- 保持页面轻量，优先保证本地查看效率。

## 后续功能

- 基于 `data/processed/YYYY-MM-DD.json` 展示线索列表。
- 按品牌、车型、来源或线索类型筛选。
- 增加日报与结构化数据之间的跳转定位。
- 增加简单统计图表。
- 增加最近日报快捷入口。

## 与现有流水线的关系

前端只消费现有产物，不改变现有命令顺序：

```powershell
python tools\scraper.py
python tools\processor.py
python tools\enrich.py
python tools\report_generator.py
python tools\validate.py --date 2026-07-03
```

日报生成完成后，前端再读取 `output/` 中的 Markdown 文件进行展示。前端问题不应阻塞抓取、处理、补充和生成日报流程。

## 文件分类规则

- `frontend/`：本地查看器源码、样式、静态资源和前端构建配置。
- `output/`：最终日报 Markdown，前端只读。
- `data/processed/`：结构化数据，前端只读。
- `tools/`：Python 流水线脚本和可选本地服务脚本。
- `logs/`：运行日志、调试页面和截图，不作为前端稳定数据源。
- `config/`：流水线配置和提示词，不放前端状态。

## 开发原则

- 先做本地可用，再考虑框架化。
- 优先使用现有日报产物，避免重复生成数据。
- 页面交互服务于查看效率，不做营销页或复杂后台。
- 前端代码与 Python 流水线解耦。
- 所有文件读写路径保持清晰，日期文件继续使用 `YYYY-MM-DD` 命名。
