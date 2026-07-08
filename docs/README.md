# docs/ - Planning and Design Notes

Read this file before searching docs. This directory holds human planning notes, not runtime code.

## Files

- `frontend-local-viewer.md`: original plan and boundaries for the local Markdown report viewer.
- `runtime-task-log.md`: runtime execution history for workbench jobs and backend agent runs.
- `README.md`: this guide.

## Agent Routing

- For current implementation status and active development context, read `progress.md` in the repository root first.
- For runtime execution history, read `docs/runtime-task-log.md`.
- For repository rules and safe workflow expectations, read `AGENTS.md`.
- For frontend rationale and historical boundaries, read `docs/frontend-local-viewer.md`.
- For executable behavior, inspect `tools/` and `frontend/`; docs may lag code.

## Maintenance

When adding a new planning document, add a one-line entry above so future agents can decide whether to open it.

Record active development work in root `progress.md`. Record runtime job history in `docs/runtime-task-log.md`. If documentation structure or repository guidance changes, update this file plus root `AGENTS.md` and `README.md`.
