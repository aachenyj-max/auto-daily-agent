#!/usr/bin/env python3
"""Generate scoped automotive reports from processed daily data."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from intent_parser import ReportTask, parse_intent


PROJECT_ROOT = Path(__file__).parent.parent
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
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


def iter_models(data: dict[str, Any]) -> list[dict[str, Any]]:
    models = []
    for brand in data.get("brands", []):
        for model in brand.get("models", []):
            item = dict(model)
            item["brand"] = brand.get("name", item.get("brand_name") or "")
            models.append(item)
    return models


def find_brand(data: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    for brand in data.get("brands", []):
        if name in brand.get("name", "") or brand.get("name", "") in name:
            return brand
    return None


def find_model(data: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    for model in iter_models(data):
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


def market_report(data: dict[str, Any], task: ReportTask) -> str:
    summary = data.get("market_summary", {})
    models = sorted(iter_models(data), key=lambda item: item.get("sales", 0), reverse=True)
    new_energy = [m for m in models if m.get("energy_type") != "燃油"]
    lines = [
        f"# 汽车市场日报 - {task.date}",
        "",
        f"> 用户需求：{task.source_prompt or '生成汽车市场日报'}",
        "",
        "## 市场概览",
        "",
        f"今日监测 {summary.get('total_models', len(models))} 款车型，新能源车型 {summary.get('new_energy_count', len(new_energy))} 款，占比 {summary.get('new_energy_ratio', 0)}%。",
        f"车型结构为轿车 {summary.get('sedan_count', 0)} 款、SUV {summary.get('suv_count', 0)} 款、MPV {summary.get('mpv_count', 0)} 款。",
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


def brand_report(data: dict[str, Any], task: ReportTask) -> str:
    brand = find_brand(data, task.brand)
    if not brand:
        return filtered_report(data, task, title=f"{task.brand or '指定品牌'}未命中，改为条件报告")
    models = sorted(
        [dict(m, brand=brand.get("name", "")) for m in brand.get("models", [])],
        key=lambda item: item.get("sales", 0),
        reverse=True,
    )
    top = models[0] if models else {}
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
        "## 购买建议",
        "",
        brand_advice(brand.get("name", ""), models),
    ]
    return "\n".join(lines)


def series_report(data: dict[str, Any], task: ReportTask) -> str:
    model = find_model(data, task.series)
    if not model:
        return filtered_report(data, task, title=f"{task.series or '指定车型'}未命中，改为条件报告")
    same_brand = [m for m in iter_models(data) if m.get("brand") == model.get("brand")]
    same_price = [
        m for m in iter_models(data)
        if m.get("name") != model.get("name") and abs(avg_price(m) - avg_price(model)) <= 5
    ]
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
        "## 购买建议",
        "",
        series_advice(model),
    ]
    return "\n".join(lines)


def compare_report(data: dict[str, Any], task: ReportTask) -> str:
    models = [find_model(data, name) for name in task.compare_series]
    models = [model for model in models if model]
    if len(models) < 2:
        return filtered_report(data, task, title="对比车型不足，改为相关车型报告")
    lines = [
        f"# 车型对比报告 - {task.date}",
        "",
        f"> 用户需求：{task.source_prompt}",
        "",
        "## 核心对比",
        "",
        *table(models, len(models)),
        "",
        "## 结论",
        "",
    ]
    best_sales = max(models, key=lambda item: item.get("sales", 0))
    cheapest = min(models, key=lambda item: item.get("price_min") or 999)
    lines.append(f"销量热度最高的是 {best_sales.get('name')}，当前样本销量 {best_sales.get('sales', 0):,}。")
    lines.append(f"价格门槛最低的是 {cheapest.get('name')}，价格区间 {cheapest.get('price', '-')}。")
    lines.append("如果你更重视风险可控，优先选择销量和服务网络更稳的车型；如果你更重视体验差异，必须试驾并核对交付周期、保险和本地售后。")
    return "\n".join(lines)


def filtered_report(data: dict[str, Any], task: ReportTask, title: str | None = None) -> str:
    models = filter_models(iter_models(data), task.filters)
    title = title or f"{describe_filters(task.filters)}购买建议 - {task.date}"
    lines = [
        f"# {title}",
        "",
        f"> 用户需求：{task.source_prompt}",
        "",
        f"共筛选出 {len(models)} 款车型。排序按销量从高到低。",
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


def generate_report(task: ReportTask) -> tuple[Path, str]:
    data = load_processed(task.date)
    if task.report_type == "brand":
        content = brand_report(data, task)
    elif task.report_type == "series":
        content = series_report(data, task)
    elif task.report_type == "compare":
        content = compare_report(data, task)
    elif task.report_type == "filtered":
        content = filtered_report(data, task)
    else:
        content = market_report(data, task)

    content += f"\n\n---\n\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    output = OUTPUT_DIR / output_name_for(task)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(content)
    return output, content


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()
    task = parse_intent(args.prompt, use_llm=args.use_llm)
    output, _ = generate_report(task)
    print(json.dumps({"task": asdict(task), "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
