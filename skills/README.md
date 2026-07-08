# skills/ - Local Reusable Skills

Read this file first before opening skill internals. These folders are helper capabilities for scraping and conversion; they are not the main daily pipeline entry points.

## Contents

```text
skills/
├── web-scraper/
│   ├── SKILL.md
│   └── scripts/main.py
├── markitdown-skill/
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
└── README.md
```

## When To Read Each Skill

- Read `web-scraper/SKILL.md` when changing HTML scraping, CSS selector extraction, link extraction, or structured page scraping.
- Read `markitdown-skill/SKILL.md` when converting HTML, JSON, PDF, Office files, or other raw artifacts to Markdown.
- Do not read all `references/` files by default. Open only the reference named by the relevant `SKILL.md` section or needed command.

## Project Usage

The current production pipeline mainly uses Python scripts in `tools/`.

- Base data comes from Dongchedi JSON APIs through `tools/scraper.py`.
- Enriched detail data is coordinated by `tools/enrich.py`.
- Skill outputs may feed `data/raw/enriched/` and `data/processed/enriched/`.
- Dynamic reports must not trust enriched config blindly; `tools/dynamic_report_generator.py` validates model/variant name matches before using it.

## Common Commands

```powershell
python skills\web-scraper\scripts\main.py scrape "https://example.com" --selector ".content"
python skills\web-scraper\scripts\main.py links "https://example.com" --internal-only
```

For MarkItDown commands, prefer the installed `markitdown` CLI if available. If it is not available, inspect `skills/markitdown-skill/SKILL.md` before installing or wiring dependencies.

## Safety Notes

- Do not commit cookies, API keys, phone numbers, session state, or captured private pages.
- Treat `data/cookies.json` and `data/session_info.json` as local-only credentials.
- If a skill fetches live websites, preserve request throttling and source attribution in generated artifacts.

## Maintenance Notes

- Before changing local skills, record the task context and follow-up state in root `progress.md`.
- If skill responsibilities, commands, or routing guidance change, update this file plus root `AGENTS.md` and `README.md`.
