#!/usr/bin/env python3
"""Parse natural-language report requests into a safe report task."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_client import chat_completion, load_yaml_file


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

REPORT_TYPES = {"market", "brand", "series", "compare", "filtered"}
TASK_ACTIONS = {"run", "ask", "refuse"}


@dataclass
class ReportTask:
    action: str = "run"
    report_type: str = "market"
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    brand: str | None = None
    series: str | None = None
    compare_series: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    focus: list[str] = field(default_factory=list)
    output_name: str | None = None
    source_prompt: str = ""
    clarifying_question: str | None = None
    workflow_notes: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)


def load_settings() -> dict[str, Any]:
    return load_yaml_file(CONFIG_DIR / "settings.yaml")


def load_workflow_prompt() -> str:
    file = CONFIG_DIR / "workflow_prompt.md"
    if not file.exists():
        return ""
    return file.read_text(encoding="utf-8")


def parse_minimal_settings(text: str) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    current_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            settings[current_section] = {}
            continue
        if current_section and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            value = value.strip().strip('"').strip("'")
            settings.setdefault(current_section, {})[key.strip()] = value
    return settings


def load_known_names(date: str | None = None) -> tuple[list[str], list[str]]:
    date = date or datetime.now().strftime("%Y-%m-%d")
    file = DATA_PROCESSED / f"{date}.json"
    brands: set[str] = set()
    series: set[str] = set()
    if not file.exists():
        return [], []
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
    for brand in data.get("brands", []):
        if brand.get("name"):
            brands.add(brand["name"])
        for model in brand.get("models", []):
            if model.get("name"):
                series.add(model["name"])
    return sorted(brands, key=len, reverse=True), sorted(series, key=len, reverse=True)


def infer_date(prompt: str) -> str:
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", prompt)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return datetime.now().strftime("%Y-%m-%d")


def parse_price_filter(prompt: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    under = re.search(r"(\d+(?:\.\d+)?)\s*万?以[内下]", prompt)
    if under:
        filters["price_max"] = float(under.group(1))
    above = re.search(r"(\d+(?:\.\d+)?)\s*万?以上", prompt)
    if above:
        filters["price_min"] = float(above.group(1))
    between = re.search(r"(\d+(?:\.\d+)?)\s*[-到至]\s*(\d+(?:\.\d+)?)\s*万", prompt)
    if between:
        filters["price_min"] = float(between.group(1))
        filters["price_max"] = float(between.group(2))
    if "SUV" in prompt.upper():
        filters["body_type"] = "SUV"
    if "轿车" in prompt:
        filters["body_type"] = "轿车"
    if "MPV" in prompt.upper():
        filters["body_type"] = "MPV"
    if "新能源" in prompt:
        filters["energy_type"] = "新能源"
    elif "纯电" in prompt:
        filters["energy_type"] = "纯电动"
    elif "插混" in prompt or "增程" in prompt:
        filters["energy_type"] = "插混/增程"
    elif "燃油" in prompt:
        filters["energy_type"] = "燃油"
    return filters


def fallback_parse(prompt: str) -> ReportTask:
    date = infer_date(prompt)
    brands, series_names = load_known_names(date)
    task = ReportTask(date=date, source_prompt=prompt, filters=parse_price_filter(prompt))

    found_series = [name for name in series_names if name and name in prompt]
    found_brands = [name for name in brands if name and name in prompt]

    wants_single_series = any(word in prompt for word in ("单车", "单车型", "车型报告", "车型分析", "分析报告"))
    wants_brand_report = bool(found_brands) and any(word in prompt for word in ("车企日报", "品牌日报", "汽车日报", "日报"))

    if any(word in prompt for word in ("对比", "比较", "PK", "pk", "vs", "VS")):
        task.report_type = "compare"
        task.compare_series = found_series[:4]
    elif wants_brand_report:
        task.report_type = "brand"
        task.brand = found_brands[0]
        task.series = None
    elif found_series:
        if wants_single_series or not found_brands:
            task.report_type = "series"
            task.series = found_series[0]
        else:
            task.report_type = "brand"
            task.brand = found_brands[0]
    elif found_brands:
        task.report_type = "brand"
        task.brand = found_brands[0]
    elif task.filters:
        task.report_type = "filtered"
    else:
        task.report_type = "market"

    focus = []
    for token in ("购买建议", "销量", "价格", "配置", "新能源", "智能化", "家庭", "通勤"):
        if token in prompt:
            focus.append(token)
    for name in found_series[:3]:
        if name not in focus:
            focus.append(name)
    task.focus = focus
    return task


def normalize_task(raw: dict[str, Any], prompt: str) -> ReportTask:
    fallback = fallback_parse(prompt)
    action = raw.get("action") if raw.get("action") in TASK_ACTIONS else fallback.action
    report_type = raw.get("report_type") if raw.get("report_type") in REPORT_TYPES else fallback.report_type
    filters = raw.get("filters") if isinstance(raw.get("filters"), dict) else fallback.filters
    task = ReportTask(
        action=action,
        report_type=report_type,
        date=raw.get("date") or fallback.date,
        brand=raw.get("brand") or fallback.brand,
        series=raw.get("series") or fallback.series,
        compare_series=raw.get("compare_series") if isinstance(raw.get("compare_series"), list) else fallback.compare_series,
        filters=filters,
        focus=raw.get("focus") if isinstance(raw.get("focus"), list) else fallback.focus,
        output_name=raw.get("output_name"),
        source_prompt=prompt,
        clarifying_question=raw.get("clarifying_question") if isinstance(raw.get("clarifying_question"), str) else None,
        workflow_notes=raw.get("workflow_notes") if isinstance(raw.get("workflow_notes"), list) else [],
        risk_notes=raw.get("risk_notes") if isinstance(raw.get("risk_notes"), list) else [],
    )
    if task.report_type == "compare" and len(task.compare_series) < 2:
        task.action = "ask"
        task.clarifying_question = task.clarifying_question or "请补充另一个用于对比的车型。"
        task.workflow_notes.append("对比报告至少需要两个车型，已暂停生成等待用户补充。")
    return task


def parse_with_llm(prompt: str, settings: dict[str, Any], api_key: str | None = None) -> ReportTask | None:
    system = load_workflow_prompt() or (
        "你是汽车报告任务解析器。只返回 JSON，不要解释。"
        "report_type 必须是 market、brand、series、compare、filtered 之一。"
        "不要返回 shell、代码或任意文件路径。"
    )
    user = {
        "prompt": prompt,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "schema": {
            "report_type": "market|brand|series|compare|filtered",
            "date": "YYYY-MM-DD",
            "brand": "品牌或车企名/null",
            "series": "单车型/null",
            "compare_series": ["车型A", "车型B"],
            "filters": {"body_type": None, "energy_type": None, "price_min": None, "price_max": None},
            "focus": ["关注点"],
        },
    }
    user["schema"].update(
        {
            "action": "run|ask|refuse",
            "clarifying_question": "需要用户确认的问题/null",
            "workflow_notes": ["工作流说明"],
            "risk_notes": ["风险或降级说明"],
        }
    )
    try:
        content = chat_completion(
            [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            api_key=api_key,
            profile="workflow",
            temperature=0.1,
            max_tokens=800,
            timeout=60,
        )
        match = re.search(r"\{.*\}", content, re.S)
        raw = json.loads(match.group(0) if match else content)
        return normalize_task(raw, prompt)
    except Exception:
        return None


def parse_intent(prompt: str, api_key: str | None = None, use_llm: bool = False) -> ReportTask:
    settings = load_settings()
    if use_llm:
        task = parse_with_llm(prompt, settings, api_key)
        if task:
            return task
    return fallback_parse(prompt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()
    task = parse_intent(args.prompt, use_llm=args.use_llm)
    print(json.dumps(asdict(task), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
