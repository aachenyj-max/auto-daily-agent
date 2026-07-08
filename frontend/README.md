# frontend/ - Local Report Workbench

Read this file before editing frontend code. The frontend is a local browser UI for viewing reports and submitting safe report-generation jobs.

## Files

- `index.html`: main workbench page.
- `src/main.js`: page controls, generation form, job polling, recent files, search wiring.
- `src/report-viewer.js`: Markdown loading/rendering/search helpers.
- `src/styles.css`: layout and visual styles.
- `public/`: static assets if added later.

## How To Run

For the full generation workbench:

```powershell
python tools\workflow_server.py
```

Or double-click `start_workbench.cmd` from the repository root to launch the local server and open the browser automatically.

Open:

```text
http://127.0.0.1:8000/frontend/
```

For read-only viewing only:

```powershell
python tools\serve_frontend.py
```

Or double-click `start_viewer.cmd` from the repository root to launch the local read-only viewer and open the browser automatically.

## API Contract

The generation UI calls same-origin endpoints served by `tools/workflow_server.py`:

- `POST /api/reports/generate`
- `GET /api/reports/jobs/<job_id>`
- `GET /api/reports/latest`
- `GET /api/reports/list`
- `GET /api/reports/<report_id>`
- `POST /api/reports/archive`
- `POST /api/reports/restore`
- `POST /api/reports/followup`
- `GET /api/llm/status` returns separate `workflow` and `report` LLM profile status objects.

Do not make the static page execute arbitrary Python or shell commands. It should only call the whitelist API.
Generation requests always send `use_llm: true`; credentials are supplied by the backend environment, not the browser.
Job status may be `done`, `failed`, `needs_input`, or `refused`. `needs_input` means the workflow model returned a clarifying question or the background agent found a quality issue that requires permission before rerun; `refused` means the request exceeded safety boundaries. The default UI stays concise and shows status, one message, and the generated report name.

The workbench now also includes a managed report list backed by `data/managed_reports/index.json`. The UI can filter reports, soft-archive them, restore them, and submit a follow-up generation request bound to a selected report.

Backend jobs are now produced by a staged whitelist agent. Job payloads may also include `agent_trace` and `agent_task_context` for debugging, even if the default UI does not render them.

## Security

- There is no API key input in the UI. Do not add one back unless there is a separate secure backend design.
- The UI may show whether workflow/report LLM profiles are configured, but must never show any API key value.
- Do not hard-code local private paths or credentials.
- Frontend should read reports from `output/` through the local server.

## Verification

```powershell
node --check frontend\src\main.js
node --check frontend\src\report-viewer.js
python tools\workflow_server.py
```

## Maintenance Notes

- Before frontend development, record the task context and intended UI/API changes in root `progress.md`; after completion, record changed files, verification commands, and any browser-check caveats.
- If frontend entry points, API calls, security behavior, or verification commands change, update this file plus root `AGENTS.md` and `README.md`.
