#!/usr/bin/env python3
"""Structured context helpers for the local report agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dynamic_report_generator import (
    build_enriched_index,
    compact_param_summary,
    filter_models,
    find_brand,
    find_model,
    get_enriched,
    iter_models,
    load_enriched,
    load_processed,
)
from intent_parser import ReportTask
from workflow_runner import DATA_ENRICHED, DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, PROJECT_ROOT


CONTEXT_FILES = (
    "AGENTS.md",
    "README.md",
    "progress.md",
    "tools/README.md",
    "config/README.md",
    "data/README.md",
    "output/README.md",
)


def read_agent_context_metadata() -> dict[str, int]:
    metadata: dict[str, int] = {}
    for rel_path in CONTEXT_FILES:
        path = PROJECT_ROOT / rel_path
        if path.exists():
            metadata[rel_path] = len(path.read_text(encoding="utf-8", errors="replace"))
    return metadata


def append_progress_entry(title: str, lines: list[str]) -> None:
    progress = PROJECT_ROOT / "progress.md"
    text = "\n".join(["", f"## {title}", "", *lines, ""])
    with open(progress, "a", encoding="utf-8") as file:
        file.write(text)


def append_runtime_entry(title: str, lines: list[str]) -> None:
    runtime_log = PROJECT_ROOT / "docs" / "runtime-task-log.md"
    text = "\n".join(["", f"## {title}", "", *lines, ""])
    with open(runtime_log, "a", encoding="utf-8") as file:
        file.write(text)


def inspect_data_artifacts(date: str) -> dict[str, Any]:
    return {
        "date": date,
        "raw_exists": (DATA_RAW / f"{date}.json").exists(),
        "processed_exists": (DATA_PROCESSED / f"{date}.json").exists(),
        "enriched_exists": (DATA_ENRICHED / f"{date}.json").exists(),
        "report_exists": (OUTPUT_DIR / f"{date}.md").exists(),
    }


def _model_snapshot(model: dict[str, Any] | None) -> dict[str, Any] | None:
    if not model:
        return None
    keys = (
        "name",
        "brand",
        "brand_name",
        "series_id",
        "sales",
        "rank",
        "last_rank",
        "price",
        "price_min",
        "price_max",
        "energy_type",
        "body_type",
    )
    return {key: model.get(key) for key in keys if key in model}


def _enriched_snapshot(series: dict[str, Any] | None) -> dict[str, Any] | None:
    if not series:
        return None
    return {
        "series_name": series.get("series_name"),
        "brand": series.get("brand"),
        "series_id": series.get("series_id"),
        "sales": series.get("sales"),
        "variant_count": series.get("variant_count"),
        "params_trusted": bool(series.get("params_trusted")),
        "param_summary": compact_param_summary(series, max_items=10),
        "variants": [
            {
                "name": variant.get("name"),
                "year": variant.get("year"),
                "guide_price": variant.get("guide_price"),
                "dealer_price": variant.get("dealer_price"),
            }
            for variant in (series.get("variants") or [])[:6]
        ],
    }


def build_task_context(task: ReportTask) -> dict[str, Any]:
    availability = inspect_data_artifacts(task.date)
    context: dict[str, Any] = {
        "date": task.date,
        "report_type": task.report_type,
        "availability": availability,
        "target": None,
        "related_models": [],
        "enriched": None,
    }
    if not availability["processed_exists"]:
        return context

    data = load_processed(task.date)
    enriched_index = build_enriched_index(load_enriched(task.date))
    models = sorted(iter_models(data), key=lambda item: item.get("sales", 0), reverse=True)

    if task.report_type == "series":
        model = find_model(data, task.series)
        context["target"] = _model_snapshot(model)
        if model:
            related = [item for item in models if item.get("brand") == model.get("brand") and item.get("name") != model.get("name")]
            context["related_models"] = [_model_snapshot(item) for item in related[:8]]
            context["enriched"] = _enriched_snapshot(get_enriched(model, enriched_index))
        return context

    if task.report_type == "brand":
        brand = find_brand(data, task.brand)
        if brand:
            brand_models = sorted(
                [dict(model, brand=brand.get("name", "")) for model in brand.get("models", [])],
                key=lambda item: item.get("sales", 0),
                reverse=True,
            )
            context["target"] = {
                "brand": brand.get("name"),
                "model_count": brand.get("model_count", len(brand_models)),
                "top_models": [_model_snapshot(item) for item in brand_models[:10]],
            }
            if brand_models:
                context["enriched"] = _enriched_snapshot(get_enriched(brand_models[0], enriched_index))
        return context

    if task.report_type == "compare":
        selected = [find_model(data, name) for name in task.compare_series]
        selected = [item for item in selected if item]
        context["target"] = [_model_snapshot(item) for item in selected]
        context["enriched"] = [_enriched_snapshot(get_enriched(item, enriched_index)) for item in selected]
        return context

    if task.report_type == "filtered":
        matched = filter_models(models, task.filters)
        context["target"] = {"filters": task.filters, "match_count": len(matched)}
        context["related_models"] = [_model_snapshot(item) for item in matched[:12]]
        context["enriched"] = [_enriched_snapshot(get_enriched(item, enriched_index)) for item in matched[:4]]
        return context

    context["target"] = {
        "market_summary": data.get("market_summary"),
        "top_models": [_model_snapshot(item) for item in models[:10]],
    }
    context["enriched"] = {
        "available_series": len(enriched_index),
        "trusted_series": sum(1 for item in enriched_index.values() if item.get("params_trusted")),
    }
    return context
