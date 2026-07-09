# tools/ - Pipeline Scripts

Read this file first when working inside `tools/`. It is a map of entry points so an agent does not need to scan every script.

## Main Workflow

Use these scripts for the standard daily pipeline:

```powershell
python tools\scraper.py
python tools\processor.py
python tools\enrich.py
python tools\report_generator.py --date 2026-07-06
python tools\validate.py --date 2026-07-06
```

- `scraper.py`: fetches Dongchedi API ranking/list data into `data/raw/YYYY-MM-DD.json`.
- `processor.py`: cleans raw API data into `data/processed/YYYY-MM-DD.json`; keeps full per-brand model lists.
- `enrich.py`: optional detail enrichment into `data/processed/enriched/YYYY-MM-DD.json`.
- `report_generator.py`: legacy LLM daily report generator using `config/report_prompt.txt`.
- `validate.py`: checks raw data, processed data, and Markdown output for a date.

## Web Workbench Workflow

Use these scripts for the local natural-language web UI:

```powershell
python tools\workflow_server.py
```

Or use `start_workbench.cmd` from the repository root for a double-click local launch that also opens the browser.
If hidden/background startup is flaky on a given Windows machine, use `run_workbench.bat` instead. It keeps the server in a visible console window so startup errors are not swallowed.
If even that wrapper is unreliable, use `run_workbench_server.bat`. It simply runs `.venv\Scripts\python.exe tools\workflow_server.py` in the current console window and is the most direct local launch path.
For persistent local use after Windows login, run `install_workbench_autostart.cmd` once. It installs a Startup shortcut that calls `start_workbench_background.cmd`, which keeps the backend listening without opening the browser.

Open:

```text
http://127.0.0.1:8000/frontend/
```

- `workflow_server.py`: local HTTP server and `/api/reports/*` API.
- `report_registry.py`: managed report index builder for list/filter/archive/follow-up metadata. Writes `data/managed_reports/index.json`.
- `agent_runner.py`: controlled background agent. It reads collaboration context, calls the whitelist workflow, checks report quality, and asks before automatic reruns.
- `workflow_runner.py`: safe whitelist orchestration for parse, data checks, generation, validation.
- `intent_parser.py`: natural-language task parser. Uses rules by default; LLM parsing only when enabled and configured.
- `dynamic_report_generator.py`: dynamic market/brand/series/compare/filter report generator. It can use an OpenAI-compatible LLM for正文生成 when enabled, and falls back to rule templates.
- `llm_client.py`: local-only LLM config loader and OpenAI-compatible HTTP client. Reads environment variables, `.env.local`, and `config/local.yaml`.

## Enriched Data Rule

`dynamic_report_generator.py` reads `data/processed/enriched/YYYY-MM-DD.json`, but configuration details are used only after model-name or variant-name validation. If validation fails, reports must say the enriched config was skipped. Do not blindly inject enriched Markdown into reports.

## Supporting Scripts

- `fetch_brand_ids.py`: updates brand IDs in `config/brands.json`.
- `run_scraper.py`, `scraper_simple.py`: older or simplified scraper variants.
- `scrape_params.py`: experimental parameter scraping by car ID.
- `generate_model_report.py`: focused model report helper.
- `login.py`: Playwright login/session helper. Treat cookies/session files as local secrets.
- `serve_frontend.py`: static viewer server for read-only report browsing, not the workflow API.
- `../start_workbench.cmd`: Windows one-click launcher for `workflow_server.py`.
- `../start_viewer.cmd`: Windows one-click launcher for `serve_frontend.py`.
- `report_template.py`: older rule template helper.

## Agent Routing

- Before editing tools, confirm the current task context in root `progress.md` and update it with the plan, completed changes, validation commands, and any remaining risk.
- If a tool change adds or changes an entry point, workflow behavior, data contract, or validation expectation, update this file plus root `AGENTS.md` and `README.md`.
- For failed web generation, start with `workflow_server.py`, `workflow_runner.py`, `intent_parser.py`, and `dynamic_report_generator.py`.
- For missing or stale data, start with `scraper.py`, `processor.py`, `enrich.py`, and `validate.py`.
- For report quality, start with `dynamic_report_generator.py` and inspect `data/processed/` plus `data/processed/enriched/`.
- For LLM issues, inspect `config/settings.yaml`, environment variables `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`, then the LLM paths in `intent_parser.py` and `dynamic_report_generator.py`.
- For web UI LLM status, inspect `/api/llm/status` and `generation.llm_used` / `generation.llm_fallback_reason` in job responses.

## Separated LLM Profiles

- `intent_parser.py` uses the `workflow` LLM profile and `config/workflow_prompt.md` when LLM parsing is enabled.
- `dynamic_report_generator.py` uses the `report` LLM profile and `config/report_agent_prompt.md` when LLM report writing is enabled.
- `llm_client.py` reads `WORKFLOW_LLM_*` and `REPORT_LLM_*` from environment variables, `.env.local`, or `config/local.yaml`; legacy `LLM_*` remains a fallback for both profiles.
- `/api/llm/status` returns separate `workflow` and `report` status objects.
- `ReportTask.action` supports `run`, `ask`, and `refuse`. `ask` returns `needs_input` without generating a report; `refuse` returns `refused`. `workflow_notes` and `risk_notes` are passed through job results for frontend display.
- Web generation now enters through `agent_runner.py`, which wraps `workflow_runner.py` with context reading and report quality checks. If quality checks fail, it returns `needs_input` instead of silently overwriting output.

## Managed Report APIs

- `GET /api/reports/list`: returns indexed report metadata with filters like `status`, `report_type`, `date_from`, `date_to`, and `keyword`.
- `GET /api/reports/<report_id>`: returns one managed report record.
- `POST /api/reports/archive`: soft-archives one or more report records. This does not physically delete Markdown files.
- `POST /api/reports/restore`: restores soft-archived report records.
- `POST /api/reports/followup`: starts a new report-generation job based on an existing managed report. Follow-up output is written to a new file to avoid overwriting the source report.

## 2026-07-07 Agentized Stages

- `workflow_runner.py` now exposes explicit stages: `plan_task()`, `ensure_daily_data()`, `generate_task_report()`, and `finalize_run_result()`.
- `agent_runner.py` no longer hides generation behind one monolithic workflow call. The backend agent now executes staged whitelist tools and records `agent_trace`.
- `tool_registry.py` is the effective control plane for staged execution:
  `read_context` -> `inspect_request` -> `inspect_data` -> `prepare_data` -> `build_context` -> `generate_report` -> `validate_report` -> `quality_check`
- `agent_core.py` remains bounded. It selects only from the registered tools and stops once `quality_check` or a non-`run` terminal action is reached.
- When debugging agentized generation, inspect both `result.agent_trace` and `result.agent_task_context` before changing report templates or parser rules.
