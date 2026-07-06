#!/usr/bin/env python3
"""Generate a detailed report for a selected brand or vehicle series."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import requests
import yaml


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_settings():
    with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_raw_cars(date):
    raw_file = DATA_RAW / f"{date}.json"
    if not raw_file.exists():
        raise FileNotFoundError(f"raw data not found: {raw_file}")
    with open(raw_file, "r", encoding="utf-8") as file:
        return json.load(file).get("cars", [])


def slugify(value):
    value = re.sub(r"\s+", "-", value.strip().lower())
    value = re.sub(r'[\\/:*?"<>|]+', "-", value)
    return value.strip("-") or "model-report"


def matches(car, brand=None, series=None, query=None):
    values = [
        car.get("brand_name", ""),
        car.get("_brand_name", ""),
        car.get("sub_brand_name", ""),
        car.get("series_name", ""),
    ]
    haystack = " ".join(str(value) for value in values)
    if brand and brand not in haystack:
        return False
    if series and series not in str(car.get("series_name", "")):
        return False
    if query and query not in haystack:
        return False
    return True


def fetch_variants(series_id, settings):
    dc = settings["dongchedi"]
    url = f"{dc['base_url']}{dc['api']['car_list']}"
    params = {
        "aid": dc["params"]["aid"],
        "app_name": dc["params"]["app_name"],
        "series_id": series_id,
    }
    response = requests.get(url, params=params, headers=dc["headers"], timeout=20)
    response.raise_for_status()
    data = response.json().get("data", {})

    variants = []
    for tab in data.get("tab_list", []):
        if tab.get("tab_key") != "online_all":
            continue
        current_group = ""
        for item in tab.get("data", []):
            info = item.get("info") or {}
            if item.get("type") == "1137" and info.get("name"):
                current_group = info["name"]
                continue
            if item.get("type") != "1115" or not info.get("car_id"):
                continue
            variants.append(
                {
                    "car_id": info.get("car_id"),
                    "year": info.get("year"),
                    "name": info.get("name", ""),
                    "price": info.get("official_price_str") or info.get("price") or "",
                    "dealer_price": info.get("dealer_price") or "",
                    "tags": info.get("tags") or [],
                    "group": current_group,
                    "group_key": info.get("car_group_list_key") or "",
                    "config_code": info.get("config_code") or "",
                    "follower_rate": (info.get("follower_rate") or {}).get("text", ""),
                }
            )
    return variants


def build_dataset(cars, settings):
    dataset = []
    seen = set()
    for car in cars:
        series_id = car.get("series_id")
        if not series_id or series_id in seen:
            continue
        seen.add(series_id)
        variants = fetch_variants(series_id, settings)
        dataset.append(
            {
                "series_id": series_id,
                "series_name": car.get("series_name", ""),
                "brand_name": car.get("brand_name") or car.get("_brand_name", ""),
                "rank": car.get("rank", 0),
                "last_rank": car.get("last_rank", 0),
                "sales": car.get("count", 0),
                "price_range": car.get("price") or car.get("dealer_price", ""),
                "variants": variants,
            }
        )
    return dataset


def price_bounds(series_list):
    prices = []
    for series in series_list:
        value = series.get("price_range")
        if not value or "-" not in str(value):
            continue
        left, right = str(value).replace("万", "").split("-", 1)
        try:
            prices.extend([float(left), float(right)])
        except ValueError:
            continue
    return (min(prices), max(prices)) if prices else (None, None)


def collect_summary(variants):
    ranges = []
    drives = set()
    energies = set()
    for variant in variants:
        text = variant["name"] + " " + " ".join(variant.get("tags", []))
        match = re.search(r"(\d{2,4})\s*KM", text, re.I)
        if match:
            ranges.append(int(match.group(1)))
        for drive in ("前驱", "后驱", "四驱"):
            if drive in text:
                drives.add(drive)
        if "增程" in text:
            energies.add("增程")
        if "插混" in text or "DM-i" in text:
            energies.add("插混")
        if "纯电" in text or ("增程" not in text and match):
            energies.add("纯电")
        if any(word in text for word in ("汽油", "柴油", "T ", "L ")):
            energies.add("燃油")
    return ranges, sorted(drives), sorted(energies)


def variant_row(variant):
    text = variant["name"] + " " + " ".join(variant.get("tags", []))
    if "增程" in text:
        energy = "增程"
    elif "插混" in text or "DM-i" in text:
        energy = "插混"
    elif "纯电" in text or re.search(r"\d{2,4}\s*KM", text, re.I):
        energy = "纯电"
    else:
        energy = "未标注"

    match = re.search(r"(\d{2,4})\s*KM", text, re.I)
    range_text = f"{match.group(1)} KM" if match else "未标注"
    labels = "、".join(variant.get("tags") or []) or "未标注"

    return (
        f"| {variant.get('group', '')} | {variant.get('name', '')} | "
        f"{variant.get('price', '')} | {variant.get('dealer_price', '')} | "
        f"{energy} | {range_text} | {labels} | 数据源未返回 | "
        f"{variant.get('follower_rate', '')} |"
    )


def write_report(series_list, title, date, output_file):
    total_sales = sum(series.get("sales") or 0 for series in series_list)
    total_variants = sum(len(series["variants"]) for series in series_list)
    leader = max(series_list, key=lambda item: item.get("sales") or 0)
    min_price, max_price = price_bounds(series_list)
    price_line = (
        f"- 价格带：{min_price:.2f}-{max_price:.2f} 万元。"
        if min_price is not None
        else "- 价格带：当前数据源未返回可计算的完整价格区间。"
    )

    lines = [
        f"# {title}日报（{date}）",
        "",
        "> 数据来源：本仓库当日懂车帝抓取结果、车系 car_list 接口。车型、价格、续航标签、驱动/座位标签来自接口；电池容量、电池类型、充电倍率等字段当前接口未返回，报告中不做推测。",
        "",
        "## 一、核心概览",
        "",
        f"- 覆盖车系：{len(series_list)} 个，车型变体：{total_variants} 款。",
        f"- 当日抓取月销量合计：{total_sales:,} 辆。",
        f"- 销量主力：{leader['series_name']}，月销量 {leader.get('sales', 0):,} 辆，价格区间 {leader.get('price_range', '')}。",
        price_line,
        "",
        "## 二、车系销量与价格",
        "",
        "| 排名 | 品牌 | 车系 | 月销量 | 上期排名 | 价格区间 | 在售/停产在售变体 |",
        "|---:|---|---|---:|---:|---|---:|",
    ]

    for series in series_list:
        lines.append(
            f"| {series.get('rank', 0)} | {series.get('brand_name', '')} | "
            f"{series['series_name']} | {series.get('sales', 0):,} | "
            f"{series.get('last_rank', 0)} | {series.get('price_range', '')} | "
            f"{len(series['variants'])} |"
        )

    lines.extend(["", "## 三、车型、动力、续航、电池明细"])

    for series in series_list:
        ranges, drives, energies = collect_summary(series["variants"])
        lines.extend(
            [
                "",
                f"### {series['series_name']}",
                "",
                f"- 月销量 {series.get('sales', 0):,} 辆；价格区间 {series.get('price_range', '')}。",
            ]
        )
        if ranges:
            lines.append(f"- 续航覆盖：{min(ranges)}-{max(ranges)} KM（按车型名/接口标签提取）。")
        if energies:
            lines.append(f"- 动力形式：{'、'.join(energies)}。")
        if drives:
            lines.append(f"- 驱动形式：{'、'.join(drives)}。")
        lines.extend(
            [
                "- 电池信息：当前接口未返回电池容量、化学体系、供应商、快充时间；需接入可靠参数页或官方配置表补齐。",
                "",
                "| 年款/分组 | 车型 | 官方指导价 | 经销商价 | 动力形式 | 续航 | 驱动/座位标签 | 电池信息 | 关注度 |",
                "|---|---|---:|---:|---|---|---|---|---|",
            ]
        )
        for variant in series["variants"]:
            lines.append(variant_row(variant))

    lines.extend(
        [
            "",
            "## 四、后续补充建议",
            "",
            "- 如需更完整的电池、电机功率、扭矩、充电时间，请接入官方配置表或修正参数页抓取逻辑。",
            "- 若查询对象是单一车型，可使用 `--series` 精确匹配；若查询品牌，可使用 `--brand`。",
        ]
    )

    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="生成指定品牌或车系的车型日报")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--brand", help="品牌关键词，例如 小鹏、比亚迪、宝马")
    parser.add_argument("--series", help="车系关键词，例如 小鹏G9、小米SU7")
    parser.add_argument("--query", help="通用关键词，同时匹配品牌和车系")
    parser.add_argument("--title", help="报告标题前缀，默认使用查询关键词")
    parser.add_argument("--slug", help="输出文件名前缀，默认由查询关键词生成")
    return parser.parse_args()


def main():
    args = parse_args()
    if not any([args.brand, args.series, args.query]):
        raise SystemExit("请至少提供 --brand、--series 或 --query 之一")

    settings = load_settings()
    raw_cars = load_raw_cars(args.date)
    selected = [
        car
        for car in raw_cars
        if matches(car, brand=args.brand, series=args.series, query=args.query)
    ]
    if not selected:
        raise SystemExit("未找到匹配的车系，请确认关键词或先运行 scraper.py")

    series_list = build_dataset(selected, settings)
    label = args.title or args.series or args.brand or args.query or "车型"
    slug = slugify(args.slug or label)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data_file = DATA_PROCESSED / f"{slug}_{args.date}.json"
    output_file = OUTPUT_DIR / f"{slug}-{args.date}.md"

    data_file.write_text(json.dumps(series_list, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(series_list, label, args.date, output_file)
    print(f"data: {data_file}")
    print(f"report: {output_file}")


if __name__ == "__main__":
    main()
