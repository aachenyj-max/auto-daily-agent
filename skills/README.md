# skills/ - 技能文件夹

存放 WorkBuddy Skill（`SKILL.md`）及其附属资源。

## 当前技能

```
skills/
├── web-scraper/             # HTML 页面抓取：CSS 选择器提取、结构化数据、链接/邮箱提取
│   ├── SKILL.md
│   └── scripts/
│       ├── main.py           # CLI 入口（scrape / links / emails / structured 四种子命令）
│       └── requirements.txt
├── markitdown-skill/        # 多格式→Markdown 转换：HTML/PDF/JSON/Excel/RSS 等 → 干净文本
│   ├── SKILL.md
│   ├── scripts/              # 批量转换等辅助脚本
│   └── references/           # API 参考、示例、CLI 参考
└── README.md
```

## 技能用途

### web-scraper — HTML 页面抓取

当前项目通过懂车帝 JSON API 获取基础数据（价格、销量、排名）。但对于 **API 不提供的详细内容**（车型参数表、评测文章、车主口碑等），需要使用 web-scraper 从 HTML 页面补充抓取。

常用命令：

```bash
# CSS 选择器提取
python skills/web-scraper/scripts/main.py scrape "https://www.dongchedi.com/auto/params-carIds-{id}" --selector ".parameter-table"

# 结构化提取（schema=product 适配汽车产品页）
python skills/web-scraper/scripts/main.py structured "https://www.dongchedi.com/auto/series/{id}" --schema product -o data/raw/model_detail.json

# 提取页面所有链接
python skills/web-scraper/scripts/main.py links "https://www.dongchedi.com/auto/library" --internal-only
```

### markitdown-skill — 多格式清洗

将 web-scraper 抓取的 HTML 页面、API 返回的 JSON 等格式统一转为 LLM 友好的 Markdown 文本。

常用命令：

```bash
# HTML → Markdown（本地文件）
markitdown data/raw/page.html -o data/processed/page.md

# URL 直接转换（一步到位）
markitdown "https://www.dongchedi.com/news/xxx" -o data/processed/news.md

# JSON → Markdown 表格
markitdown data/raw/2025-07-02.json -o data/processed/cars.md
```

## 两技能在日报管线中的位置

```
懂车帝 JSON API ──→ scraper.py ──→ data/raw/YYYY-MM-DD.json ──→ processor.py ──→ report_generator.py ──→ 日报
                                                                                          ↑
懂车帝 HTML 页面 ──→ web-scraper ──→ 原始 HTML / JSON ──→ markitdown ──→ 干净 Markdown ──┘
                  （补充详情抓取）                        （清洗转换）         （汇入 LLM 上下文）
```

- **API 管线**（主）：获取价格、销量、排名等结构化数据 — 快速高效
- **HTML 补充管线**（辅）：抓取车型参数、评测文章等富文本 — 用 web-scraper 抓、markitdown 清洗，让日报更有深度
