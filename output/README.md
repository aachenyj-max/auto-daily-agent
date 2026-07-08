# output/ - Generated Markdown Reports

Read this file before opening generated reports. This directory is output-only for report artifacts.

## Naming

- `YYYY-MM-DD.md`: market daily report for a date.
- `brand-<brand>-YYYY-MM-DD.md`: brand report.
- `series-<series>-YYYY-MM-DD.md`: single model/series report.
- `compare-<series-a>-vs-<series-b>-YYYY-MM-DD.md`: comparison report.
- `filtered-<filters>-YYYY-MM-DD.md`: filtered buying advice.
- `*-followup-<HHMMSS>.md`: follow-up report generated from a managed report context without overwriting the original source file.

## Producers

- `tools/report_generator.py`: legacy LLM daily report generator.
- `tools/dynamic_report_generator.py`: dynamic web-workbench reports.
- `tools/workflow_runner.py`: orchestrates generation and validation for the web workbench.

## Consumers

- `frontend/` renders Markdown from this directory.
- `tools/validate.py` checks that the expected report exists and is non-empty.

## Agent Routing

- To inspect what the user sees, open the relevant `.md` file here.
- To change report logic, edit `tools/dynamic_report_generator.py` or `tools/report_generator.py`, not files in `output/`.
- Generated reports may be overwritten by rerunning workflows.
- Managed follow-up requests in the workbench should create a new follow-up file instead of replacing the source report.

## Maintenance Notes

- Before changing report naming or generated-output expectations, record the task context in root `progress.md`; after generation, record output paths and validation results.
- If output naming, producer behavior, or consumer expectations change, update this file plus root `AGENTS.md` and `README.md`.
