#!/usr/bin/env python3
"""Generate scoped automotive reports from processed daily data."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from intent_parser import ReportTask, parse_intent
from llm_client import chat_completion, load_llm_config, load_yaml_file


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_ENRICHED = DATA_PROCESSED / "enriched"
OUTPUT_DIR = PROJECT_ROOT / "output"

SLUG_MAP = {
    "比亚迪": "byd",
    "理想汽车": "li-auto",
    "理想": "li-auto",
    "蔚来": "nio",
    "小鹏汽车": "xpeng",
    "小鹏": "xpeng",
    "小米汽车": "xiaomi",
    "小米": "xiaomi",
    "宝马": "bmw",
    "奔驰": "benz",
    "奥迪": "audi",
    "丰田": "toyota",
    "本田": "honda",
    "大众": "volkswagen",
    "日产": "nissan",
}


def load_processed(date: str) -> dict[str, Any]:
    file = DATA_PROCESSED / f"{date}.json"
    if not file.exists():
        raise FileNotFoundError(f"processed data not found: {file}")
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_settings() -> dict[str, Any]:
    return load_yaml_file(CONFIG_DIR / "settings.yaml")


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


def load_report_prompt() -> str:
    for name in ("report_agent_prompt.md", "agent_prompt.md"):
        file = CONFIG_DIR / name
        if file.exists():
            return file.read_text(encoding="utf-8")
    return ""


def load_enriched(date: str) -> dict[str, Any] | None:
    file = DATA_ENRICHED / f"{date}.json"
    if not file.exists():
        return None
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_models(data: dict[str, Any]) -> list[dict[str, Any]]:
    models = []
    for brand in data.get("brands", []):
        for model in brand.get("models", []):
            item = dict(model)
            item["brand"] = brand.get("name", item.get("brand_name") or "")
            models.append(item)
    return models


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s·・\-_/（）()]+", "", value).lower()


def series_aliases(series: dict[str, Any]) -> set[str]:
    names = {series.get("series_name") or ""}
    for variant in series.get("variants", [])[:30]:
        name = variant.get("name")
        if name:
            names.add(name)
    aliases = {normalize_name(name) for name in names if normalize_name(name)}
    return {alias for alias in aliases if len(alias) >= 2}


def params_match_series(series: dict[str, Any]) -> bool:
    params = series.get("params") or {}
    text = ""
    if params.get("markdown"):
        markdown_lines = str(params["markdown"]).splitlines()
        if markdown_lines and markdown_lines[0].lstrip().startswith("##"):
            markdown_lines = markdown_lines[1:]
        text += "\n".join(markdown_lines)
    structured = params.get("structured")
    if structured:
        text += json.dumps(structured, ensure_ascii=False)
    normalized_text = normalize_name(text)
    if not normalized_text:
        return False
    return any(alias in normalized_text for alias in series_aliases(series))


def build_enriched_index(enriched: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not enriched:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for series in enriched.get("series", []):
        sid = series.get("series_id")
        if sid is None:
            continue
        trusted = params_match_series(series)
        item = dict(series)
        item["params_trusted"] = trusted
        index[str(sid)] = item
    return index


def get_enriched(model: dict[str, Any], enriched_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    sid = model.get("series_id")
    if sid is None:
        return None
    return enriched_index.get(str(sid))


def compact_param_summary(series: dict[str, Any] | None, max_items: int = 12) -> list[str]:
    if not series:
        return []
    params = series.get("params") or {}
    if not series.get("params_trusted"):
        if params:
            return ["补充配置数据存在，但未通过车型匹配校验，已跳过。"]
        return []
    structured = params.get("structured") or {}
    wanted = (
        "基本信息", "车身", "发动机", "电动机", "变速箱", "底盘/转向", "车轮/制动",
        "主动安全", "被动安全", "辅助/操控配置", "内部配置", "座椅配置",
        "智能互联", "智能化配置", "续航", "充电",
    )
    lines: list[str] = []
    for category, values in structured.items():
        if len(lines) >= max_items:
            break
        if not any(key in category for key in wanted) or not isinstance(values, dict):
            continue
        for key, value in values.items():
            if len(lines) >= max_items:
                break
            value_text = str(value).strip()
            if not value_text or value_text in {"-", "无", "None"}:
                continue
            lines.append(f"- {category} / {key}: {value_text}")
    if lines:
        return lines

    variants = [v for v in series.get("variants", []) if v.get("car_id")]
    if variants:
        return [f"- 在售/历史版本样本：{', '.join(v.get('name', '') for v in variants[:8])}"]
    return []


def enriched_context_for_task(
    task: ReportTask,
    data: dict[str, Any],
    enriched_index: dict[str, dict[str, Any]],
    max_series: int = 6,
) -> str:
    selected: list[dict[str, Any]] = []
    if task.report_type == "series":
        model = find_model(data, task.series)
        enriched = get_enriched(model or {}, enriched_index)
        if enriched:
            selected.append(enriched)
    elif task.report_type == "brand":
        brand = find_brand(data, task.brand)
        if brand:
            for model in brand.get("models", [])[:max_series]:
                enriched = get_enriched(model, enriched_index)
                if enriched:
                    selected.append(enriched)
    elif task.report_type == "compare":
        for name in task.compare_series:
            model = find_model(data, name)
            enriched = get_enriched(model or {}, enriched_index)
            if enriched:
                selected.append(enriched)
    else:
        selected = list(enriched_index.values())[:max_series]

    sections = []
    for series in selected[:max_series]:
        params_state = "trusted" if series.get("params_trusted") else "untrusted"
        lines = [
            f"### {series.get('series_name', '-')}",
            f"- series_id: {series.get('series_id')}",
            f"- brand: {series.get('brand', '-')}",
            f"- sales: {series.get('sales', '-')}",
            f"- params_state: {params_state}",
        ]
        lines.extend(compact_param_summary(series, max_items=16))
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def model_brief(model: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "name",
        "brand",
        "brand_name",
        "series_id",
        "price",
        "price_min",
        "price_max",
        "sales",
        "rank",
        "last_rank",
        "energy_type",
        "body_type",
    )
    return {key: model.get(key) for key in keys if key in model}


def brand_brief(brand: dict[str, Any]) -> dict[str, Any]:
    models = sorted(
        [dict(model, brand=brand.get("name", "")) for model in brand.get("models", [])],
        key=lambda item: item.get("sales", 0),
        reverse=True,
    )
    return {
        "name": brand.get("name"),
        "model_count": brand.get("model_count", len(models)),
        "top_models": [model_brief(model) for model in models[:8]],
    }


def build_llm_data_context(task: ReportTask, data: dict[str, Any]) -> dict[str, Any]:
    models = sorted(iter_models(data), key=lambda item: item.get("sales", 0), reverse=True)
    base: dict[str, Any] = {
        "report_date": data.get("report_date"),
        "market_summary": data.get("market_summary"),
        "task_type": task.report_type,
    }

    if task.report_type == "series":
        target = find_model(data, task.series)
        if not target:
            base["target_model"] = None
            base["candidate_models"] = [model_brief(model) for model in models[:20]]
            return base
        same_brand = [
            model for model in models
            if model.get("brand") == target.get("brand")
        ]
        same_price = [
            model for model in models
            if model.get("name") != target.get("name") and abs(avg_price(model) - avg_price(target)) <= 5
        ]
        base.update(
            {
                "target_model": model_brief(target),
                "same_brand_models": [model_brief(model) for model in same_brand[:10]],
                "near_price_competitors": [model_brief(model) for model in same_price[:10]],
            }
        )
        return base

    if task.report_type == "brand":
        brand = find_brand(data, task.brand)
        base["target_brand"] = brand_brief(brand) if brand else None
        base["market_top_models"] = [model_brief(model) for model in models[:15]]
        return base

    if task.report_type == "compare":
        selected = [find_model(data, name) for name in task.compare_series]
        selected = [model for model in selected if model]
        base["compare_models"] = [model_brief(model) for model in selected]
        if selected:
            brands = {model.get("brand") for model in selected}
            related = [
                model for model in models
                if model.get("brand") in brands and model.get("name") not in {item.get("name") for item in selected}
            ]
            base["related_models"] = [model_brief(model) for model in related[:12]]
        return base

    if task.report_type == "filtered":
        filtered = filter_models(models, task.filters)
        base["filters"] = task.filters
        base["matched_models"] = [model_brief(model) for model in filtered[:25]]
        return base

    base["market_top_models"] = [model_brief(model) for model in models[:30]]
    base["brand_summaries"] = [brand_brief(brand) for brand in data.get("brands", [])[:12]]
    return base


def llm_config(api_key: str | None = None) -> tuple[str | None, str | None, str | None]:
    config = load_llm_config(api_key, profile="report")
    return config.api_key, config.api_base, config.model


def generate_report_with_llm(
    task: ReportTask,
    data: dict[str, Any],
    enriched_index: dict[str, dict[str, Any]],
    api_key: str | None,
) -> str | None:
    slim_data = build_llm_data_context(task, data)
    context = enriched_context_for_task(task, data, enriched_index)
    system = load_report_prompt() or (
        "你是一位严谨的汽车行业分析师。根据给定 JSON 数据生成中文 Markdown 报告。"
        "不得编造未提供的销量、价格或配置。"
        "params_state 为 untrusted 的补充配置只能说明已跳过，不能当作真实配置引用。"
    )
    user = {
        "task": asdict(task),
        "data": slim_data,
        "trusted_enriched_context": context,
        "requirements": [
            "保留用户需求指向，按报告类型组织内容。",
            "尽量写出具体车型、价格、销量、配置关注点和购买建议。",
            "如果配置数据不可信，明确说明补充配置未通过校验。",
            "输出完整 Markdown，不要输出 JSON。",
        ],
    }
    content = chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        api_key=api_key,
        profile="report",
        temperature=0.4,
        max_tokens=4000,
        timeout=120,
    )
    return content or None


def find_brand(data: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    for brand in data.get("brands", []):
        if name in brand.get("name", "") or brand.get("name", "") in name:
            return brand
    return None


def normalize_model_query(value: str | None) -> str:
    if not value:
        return ""
    normalized = normalize_name(value)
    for prefix in ("xiaopeng", "xpeng", "小鹏汽车", "小鹏"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    return normalized


def find_model(data: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    models = iter_models(data)
    query = normalize_model_query(name)
    if query:
        for model in models:
            if normalize_model_query(model.get("name", "")) == query:
                return model
    for model in models:
        model_name = model.get("name", "")
        if name in model_name or model_name in name:
            return model
    return None


def avg_price(model: dict[str, Any]) -> float:
    return ((model.get("price_min") or 0) + (model.get("price_max") or 0)) / 2


def filter_models(models: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for model in models:
        if filters.get("body_type") and model.get("body_type") != filters["body_type"]:
            continue
        energy = filters.get("energy_type")
        if energy:
            model_energy = model.get("energy_type") or ""
            if energy == "新能源":
                if model_energy == "燃油":
                    continue
            elif energy not in model_energy:
                continue
        price_min = filters.get("price_min")
        price_max = filters.get("price_max")
        if price_min is not None and (model.get("price_max") or 0) < float(price_min):
            continue
        if price_max is not None and (model.get("price_min") or 0) > float(price_max):
            continue
        result.append(model)
    return sorted(result, key=lambda item: item.get("sales", 0), reverse=True)


def safe_slug(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    value = SLUG_MAP.get(value, value)
    value = re.sub(r"\s+", "-", value.strip().lower())
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = value.strip("-")
    return value or fallback


def output_name_for(task: ReportTask) -> str:
    if task.output_name:
        return Path(task.output_name).name
    date = task.date
    if task.report_type == "market":
        return f"{date}.md"
    if task.report_type == "brand":
        return f"brand-{safe_slug(task.brand, 'brand')}-{date}.md"
    if task.report_type == "series":
        return f"series-{safe_slug(task.series, 'series')}-{date}.md"
    if task.report_type == "compare":
        names = "-vs-".join(safe_slug(name, "model") for name in task.compare_series[:3])
        return f"compare-{names or 'models'}-{date}.md"
    return f"filtered-{safe_slug(describe_filters(task.filters), 'models')}-{date}.md"


def money(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def model_row(model: dict[str, Any], rank: int | None = None) -> str:
    prefix = str(rank) if rank is not None else "-"
    return (
        f"| {prefix} | {model.get('name', '-')} | {model.get('brand', model.get('brand_name', '-'))} | "
        f"{model.get('sales', 0):,} | {money(model.get('price'))} | "
        f"{model.get('energy_type', '-')} | {model.get('body_type', '-')} |"
    )


def table(models: list[dict[str, Any]], limit: int = 10) -> list[str]:
    lines = [
        "| 排名 | 车型 | 品牌 | 销量 | 价格区间 | 能源 | 车身 |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for i, model in enumerate(models[:limit], 1):
        lines.append(model_row(model, i))
    return lines


def describe_filters(filters: dict[str, Any]) -> str:
    parts = []
    if filters.get("body_type"):
        parts.append(str(filters["body_type"]))
    if filters.get("energy_type"):
        parts.append(str(filters["energy_type"]))
    if filters.get("price_min") is not None and filters.get("price_max") is not None:
        parts.append(f"{filters['price_min']}-{filters['price_max']}万")
    elif filters.get("price_max") is not None:
        parts.append(f"{filters['price_max']}万以内")
    elif filters.get("price_min") is not None:
        parts.append(f"{filters['price_min']}万以上")
    return " ".join(parts) or "筛选车型"


def market_report(data: dict[str, Any], task: ReportTask, enriched_index: dict[str, dict[str, Any]]) -> str:
    summary = data.get("market_summary", {})
    models = sorted(iter_models(data), key=lambda item: item.get("sales", 0), reverse=True)
    new_energy = [m for m in models if m.get("energy_type") != "燃油"]
    trusted_count = sum(1 for item in enriched_index.values() if item.get("params_trusted"))
    lines = [
        f"# 汽车市场日报 - {task.date}",
        "",
        f"> 用户需求：{task.source_prompt or '生成汽车市场日报'}",
        "",
        "## 市场概览",
        "",
        f"今日监测 {summary.get('total_models', len(models))} 款车型，新能源车型 {summary.get('new_energy_count', len(new_energy))} 款，占比 {summary.get('new_energy_ratio', 0)}%。",
        f"车型结构为轿车 {summary.get('sedan_count', 0)} 款、SUV {summary.get('suv_count', 0)} 款、MPV {summary.get('mpv_count', 0)} 款。",
        f"补充配置数据覆盖 {len(enriched_index)} 个车系，其中 {trusted_count} 个通过车型匹配校验。",
        "",
        "## 销量前十",
        "",
        *table(models, 10),
        "",
        "## 购买建议",
        "",
        "有固定充电条件时，优先比较高销量纯电和插混车型；没有稳定充电条件时，优先看插混/增程或成熟燃油车。下订前重点核对终端成交价、保险、交付周期和本地售后。",
    ]
    return "\n".join(lines)


def brand_report(data: dict[str, Any], task: ReportTask, enriched_index: dict[str, dict[str, Any]]) -> str:
    brand = find_brand(data, task.brand)
    if not brand:
        return filtered_report(data, task, enriched_index, title=f"{task.brand or '指定品牌'}未命中，改为条件报告")
    models = sorted(
        [dict(m, brand=brand.get("name", "")) for m in brand.get("models", [])],
        key=lambda item: item.get("sales", 0),
        reverse=True,
    )
    top = models[0] if models else {}
    config_lines = compact_param_summary(get_enriched(top, enriched_index), max_items=10)
    lines = [
        f"# {brand.get('name')}日报 - {task.date}",
        "",
        f"> 用户需求：{task.source_prompt}",
        "",
        "## 品牌概览",
        "",
        f"样本内共有 {brand.get('model_count', len(models))} 款车型。主力车型是 {top.get('name', '-')}，销量 {top.get('sales', 0):,}，价格区间 {top.get('price', '-')}。",
        "",
        "## 车型表现",
        "",
        *table(models, 12),
        "",
    ]
    if config_lines:
        lines.extend([
            "## 主力车型配置摘要",
            "",
            *config_lines,
            "",
        ])
    lines.extend([
        "## 购买建议",
        "",
        brand_advice(brand.get("name", ""), models),
    ])
    return "\n".join(lines)


def series_report(data: dict[str, Any], task: ReportTask, enriched_index: dict[str, dict[str, Any]]) -> str:
    model = find_model(data, task.series)
    if not model:
        return filtered_report(data, task, enriched_index, title=f"{task.series or '指定车型'}未命中，改为条件报告")
    same_brand = [m for m in iter_models(data) if m.get("brand") == model.get("brand")]
    same_price = [
        m for m in iter_models(data)
        if m.get("name") != model.get("name") and abs(avg_price(m) - avg_price(model)) <= 5
    ]
    config_lines = compact_param_summary(get_enriched(model, enriched_index), max_items=16)
    lines = [
        f"# {model.get('name')}单车分析 - {task.date}",
        "",
        f"> 用户需求：{task.source_prompt}",
        "",
        "## 基本面",
        "",
        f"{model.get('name')} 属于 {model.get('brand')}，价格区间 {model.get('price', '-')}，能源类型 {model.get('energy_type', '-')}，车身类型 {model.get('body_type', '-')}，销量 {model.get('sales', 0):,}。",
        "",
        "## 同品牌参考",
        "",
        *table(sorted(same_brand, key=lambda item: item.get("sales", 0), reverse=True), 8),
        "",
        "## 近价位竞品",
        "",
        *table(sorted(same_price, key=lambda item: item.get("sales", 0), reverse=True), 8),
        "",
    ]
    if config_lines:
        lines.extend([
            "## 配置摘要",
            "",
            *config_lines,
            "",
        ])
    lines.extend([
        "## 购买建议",
        "",
        series_advice(model),
    ])
    return "\n".join(lines)


def compare_report(data: dict[str, Any], task: ReportTask, enriched_index: dict[str, dict[str, Any]]) -> str:
    models = [find_model(data, name) for name in task.compare_series]
    models = [model for model in models if model]
    if len(models) < 2:
        return filtered_report(data, task, enriched_index, title="对比车型不足，改为相关车型报告")
    lines = [
        f"# 车型对比报告 - {task.date}",
        "",
        f"> 用户需求：{task.source_prompt}",
        "",
        "## 核心对比",
        "",
        *table(models, len(models)),
        "",
        "## 配置摘要",
        "",
    ]
    has_config = False
    for model in models:
        config_lines = compact_param_summary(get_enriched(model, enriched_index), max_items=6)
        if config_lines:
            has_config = True
            lines.append(f"### {model.get('name')}")
            lines.extend(config_lines)
            lines.append("")
    if not has_config:
        lines.append("补充配置数据暂未命中或未通过车型匹配校验。")
        lines.append("")
    lines.extend([
        "## 结论",
        "",
    ])
    best_sales = max(models, key=lambda item: item.get("sales", 0))
    cheapest = min(models, key=lambda item: item.get("price_min") or 999)
    lines.append(f"销量热度最高的是 {best_sales.get('name')}，当前样本销量 {best_sales.get('sales', 0):,}。")
    lines.append(f"价格门槛最低的是 {cheapest.get('name')}，价格区间 {cheapest.get('price', '-')}。")
    lines.append("如果你更重视风险可控，优先选择销量和服务网络更稳的车型；如果你更重视体验差异，必须试驾并核对交付周期、保险和本地售后。")
    return "\n".join(lines)


def filtered_report(
    data: dict[str, Any],
    task: ReportTask,
    enriched_index: dict[str, dict[str, Any]],
    title: str | None = None,
) -> str:
    models = filter_models(iter_models(data), task.filters)
    title = title or f"{describe_filters(task.filters)}购买建议 - {task.date}"
    trusted_hits = sum(
        1 for model in models[:15]
        if (get_enriched(model, enriched_index) or {}).get("params_trusted")
    )
    lines = [
        f"# {title}",
        "",
        f"> 用户需求：{task.source_prompt}",
        "",
        f"共筛选出 {len(models)} 款车型。排序按销量从高到低。",
        f"前 15 款中有 {trusted_hits} 款命中可信补充配置。",
        "",
        *table(models, 15),
        "",
        "## 购买建议",
        "",
    ]
    if models:
        lines.append(f"优先试驾前三名：{', '.join(m.get('name', '-') for m in models[:3])}。")
        lines.append("下订前不要只看指导价，应同时比较实际成交价、保险、金融成本、交付周期和售后便利性。")
    else:
        lines.append("当前条件下没有命中车型，建议放宽价格或车身/能源限制后重新生成。")
    return "\n".join(lines)


def brand_advice(brand_name: str, models: list[dict[str, Any]]) -> str:
    if not models:
        return "当前品牌没有可用车型数据。"
    top = models[0]
    if brand_name in {"比亚迪", "小鹏汽车", "小米汽车", "理想汽车", "蔚来"}:
        return f"优先从 {top.get('name')} 开始试驾，再按预算比较同品牌其他车型。新能源车型要重点确认补能条件、保险报价、交付周期和售后网点。"
    return f"优先比较 {top.get('name')} 的终端优惠和主销配置。燃油车要重点核对库存车日期、保养成本、保险和保值率。"


def series_advice(model: dict[str, Any]) -> str:
    energy = model.get("energy_type", "")
    if energy == "燃油":
        return "这类车型适合补能便利、长期稳定使用优先的用户。购买时重点谈终端优惠、库存日期、保养套餐和置换补贴。"
    return "这类车型适合有稳定充电条件或明确新能源使用场景的用户。购买时重点确认真实续航、保险报价、交付周期、电池质保和本地售后。"


def generate_report(
    task: ReportTask,
    enriched_index: dict[str, dict[str, Any]] | None = None,
    api_key: str | None = None,
    use_llm: bool = False,
) -> tuple[Path, str, dict[str, Any]]:
    data = load_processed(task.date)
    if enriched_index is None:
        enriched_index = build_enriched_index(load_enriched(task.date))

    content = None
    generation_meta: dict[str, Any] = {
        "llm_requested": use_llm,
        "llm_used": False,
        "llm_fallback_reason": "",
        "llm_status": load_llm_config(api_key, profile="report").public_status(),
    }
    if use_llm:
        try:
            content = generate_report_with_llm(task, data, enriched_index, api_key)
            if content:
                generation_meta["llm_used"] = True
        except Exception as exc:
            content = None
            generation_meta["llm_fallback_reason"] = str(exc)

    if not content:
        if task.report_type == "brand":
            content = brand_report(data, task, enriched_index)
        elif task.report_type == "series":
            content = series_report(data, task, enriched_index)
        elif task.report_type == "compare":
            content = compare_report(data, task, enriched_index)
        elif task.report_type == "filtered":
            content = filtered_report(data, task, enriched_index)
        else:
            content = market_report(data, task, enriched_index)

    content += f"\n\n---\n\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    output = OUTPUT_DIR / output_name_for(task)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(content)
    return output, content, generation_meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--api-key")
    args = parser.parse_args()
    task = parse_intent(args.prompt, api_key=args.api_key, use_llm=args.use_llm)
    output, _, meta = generate_report(task, api_key=args.api_key, use_llm=args.use_llm)
    print(json.dumps({"task": asdict(task), "output": str(output), "generation": meta}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
