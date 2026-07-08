#!/usr/bin/env python3
"""Safe staged workflow runner for natural-language report generation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dynamic_report_generator import generate_report
from intent_parser import ReportTask, parse_intent


PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_ENRICHED = DATA_PROCESSED / "enriched"
OUTPUT_DIR = PROJECT_ROOT / "output"
TOOLS_DIR = PROJECT_ROOT / "tools"

ProgressCallback = Callable[[str, str, int], None]


def noop_progress(step: str, message: str, progress: int) -> None:
    print(f"[{progress:>3}%] {step}: {message}")


def run_script(script_name: str, progress: ProgressCallback, step: str, message: str) -> None:
    progress(step, message, 0)
    cmd = [sys.executable, str(TOOLS_DIR / script_name)]
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{script_name} failed: {detail}")


def inspect_data_artifacts(date: str) -> dict[str, Any]:
    return {
        "date": date,
        "raw_exists": (DATA_RAW / f"{date}.json").exists(),
        "processed_exists": (DATA_PROCESSED / f"{date}.json").exists(),
        "enriched_exists": (DATA_ENRICHED / f"{date}.json").exists(),
        "report_exists": (OUTPUT_DIR / f"{date}.md").exists(),
    }


def plan_task(
    prompt: str,
    api_key: str | None = None,
    use_llm: bool = False,
    progress: ProgressCallback | None = None,
) -> ReportTask:
    progress = progress or noop_progress
    progress("parse", "Parsing request into a report task", 5)
    task = parse_intent(prompt, api_key=api_key, use_llm=use_llm)
    progress("parse", f"Planned task type: {task.report_type}", 12)
    return task


def build_non_run_result(task: ReportTask, use_llm: bool) -> dict[str, Any]:
    if task.action == "ask":
        message = task.clarifying_question or "More information is required before generation can continue."
        fallback_reason = "workflow requires clarification"
    else:
        message = task.clarifying_question or "The request exceeds workflow safety boundaries."
        fallback_reason = "workflow refused unsafe request"

    return {
        "task": asdict(task),
        "action": task.action,
        "message": message,
        "workflow_notes": task.workflow_notes,
        "risk_notes": task.risk_notes,
        "output_file": None,
        "output_name": None,
        "size": 0,
        "validation": {"ok": False, "checks": {}},
        "generation": {
            "llm_requested": use_llm,
            "llm_used": False,
            "llm_fallback_reason": fallback_reason,
        },
    }


def ensure_daily_data(task: ReportTask, progress: ProgressCallback) -> dict[str, Any]:
    status = inspect_data_artifacts(task.date)
    today = datetime.now().strftime("%Y-%m-%d")

    if not status["raw_exists"]:
        if task.date != today:
            raise FileNotFoundError(
                f"Missing raw data for {task.date}. Automatic scraping is limited to today's date ({today})."
            )
        run_script("scraper.py", progress, "scrape", "Fetching today's source data")
        status = inspect_data_artifacts(task.date)
    else:
        progress("scrape", "Raw data already exists; skipping scrape", 20)

    if not status["processed_exists"]:
        run_script("processor.py", progress, "process", "Processing structured data")
        status = inspect_data_artifacts(task.date)
    else:
        progress("process", "Processed data already exists; skipping processing", 40)

    if not status["enriched_exists"] and task.date == today:
        run_script("enrich.py", progress, "enrich", "Collecting enriched model details")
        status = inspect_data_artifacts(task.date)
    elif status["enriched_exists"]:
        progress("enrich", "Enriched data already exists; skipping enrichment", 60)
    else:
        progress("enrich", "Historical date without enrichment; continuing with base report", 60)

    return status


def generate_task_report(
    task: ReportTask,
    api_key: str | None = None,
    use_llm: bool = False,
    progress: ProgressCallback | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    progress = progress or noop_progress
    progress("generate", "Generating Markdown report", 78)
    return generate_report(task, api_key=api_key, use_llm=use_llm)


def validate_outputs(date: str, output: Path) -> dict[str, Any]:
    checks = {
        "raw": (DATA_RAW / f"{date}.json").exists(),
        "processed": (DATA_PROCESSED / f"{date}.json").exists(),
        "report": output.exists() and output.stat().st_size > 0,
    }
    return {"ok": all(checks.values()), "checks": checks}


def finalize_run_result(
    task: ReportTask,
    output: Path,
    content: str,
    generation: dict[str, Any],
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    progress = progress or noop_progress
    progress("validate", "Validating generated artifacts", 92)
    validation = validate_outputs(task.date, output)
    if not validation["ok"]:
        raise RuntimeError(f"Validation failed: {validation['checks']}")

    result = {
        "task": asdict(task),
        "action": "run",
        "message": "Report generated.",
        "workflow_notes": task.workflow_notes,
        "risk_notes": task.risk_notes,
        "output_file": str(output.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "output_name": output.name,
        "size": len(content),
        "validation": validation,
        "generation": generation,
    }
    progress("done", "Report generation completed", 100)
    return result


def run_workflow(
    prompt: str,
    api_key: str | None = None,
    use_llm: bool = False,
    progress: ProgressCallback | None = None,
    task_override: ReportTask | None = None,
) -> dict[str, Any]:
    progress = progress or noop_progress
    task = task_override or plan_task(prompt, api_key=api_key, use_llm=use_llm, progress=progress)

    if task.action != "run":
        progress(task.action, task.clarifying_question or task.action, 100)
        return build_non_run_result(task, use_llm=use_llm)

    ensure_daily_data(task, progress)
    output, content, generation = generate_task_report(task, api_key=api_key, use_llm=use_llm, progress=progress)
    return finalize_run_result(task, output, content, generation, progress=progress)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()
    result = run_workflow(args.prompt, use_llm=args.use_llm)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
