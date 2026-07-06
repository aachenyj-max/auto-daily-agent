#!/usr/bin/env python3
"""Safe workflow runner for natural-language report generation."""

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
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{script_name} failed: {detail}")


def ensure_daily_data(date: str, progress: ProgressCallback) -> None:
    raw_file = DATA_RAW / f"{date}.json"
    processed_file = DATA_PROCESSED / f"{date}.json"
    enriched_file = DATA_ENRICHED / f"{date}.json"
    today = datetime.now().strftime("%Y-%m-%d")

    if not raw_file.exists():
        if date != today:
            raise FileNotFoundError(f"缺少 {date} 原始数据，自动抓取只支持当天数据")
        run_script("scraper.py", progress, "scrape", "正在抓取懂车帝数据")
    else:
        progress("scrape", "已存在原始数据，跳过抓取", 20)

    if not processed_file.exists():
        run_script("processor.py", progress, "process", "正在清洗并结构化数据")
    else:
        progress("process", "已存在结构化数据，跳过清洗", 40)

    if not enriched_file.exists() and date == today:
        run_script("enrich.py", progress, "enrich", "正在补充重点车系详情")
    elif enriched_file.exists():
        progress("enrich", "已存在补充数据，跳过补充抓取", 60)
    else:
        progress("enrich", "历史日期未补充，继续生成基础报告", 60)


def validate_outputs(date: str, output: Path) -> dict[str, Any]:
    checks = {
        "raw": (DATA_RAW / f"{date}.json").exists(),
        "processed": (DATA_PROCESSED / f"{date}.json").exists(),
        "report": output.exists() and output.stat().st_size > 0,
    }
    return {"ok": all(checks.values()), "checks": checks}


def run_workflow(
    prompt: str,
    api_key: str | None = None,
    use_llm: bool = False,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    progress = progress or noop_progress
    progress("parse", "正在解析生成需求", 5)
    task: ReportTask = parse_intent(prompt, api_key=api_key, use_llm=use_llm)
    progress("parse", f"任务类型：{task.report_type}", 12)

    ensure_daily_data(task.date, progress)

    progress("generate", "正在生成 Markdown 报告", 78)
    output, content = generate_report(task)
    progress("validate", "正在校验生成结果", 92)
    validation = validate_outputs(task.date, output)
    if not validation["ok"]:
        raise RuntimeError(f"校验失败: {validation['checks']}")

    result = {
        "task": asdict(task),
        "output_file": str(output.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "output_name": output.name,
        "size": len(content),
        "validation": validation,
    }
    progress("done", "报告已生成", 100)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()
    result = run_workflow(args.prompt, use_llm=args.use_llm)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
