#!/usr/bin/env python3
"""
懂车帝车型数据抓取脚本（简化版）
用法: python tools/scraper_simple.py
输出: 打印 JSON 到 stdout，重定向保存或用 Write 工具保存
"""

import json
import time
import requests
import yaml
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

with open(CONFIG_DIR / "brands.json", "r", encoding="utf-8") as f:
    BRANDS_CONFIG = json.load(f)


def fetch_cars_by_brand(brand_id, brand_name):
    """按品牌 ID 抓取车型数据"""
    url = f"{SETTINGS['dongchedi']['base_url']}{SETTINGS['dongchedi']['api']['rank_data']}"
    params = {
        "aid": SETTINGS["dongchedi"]["params"]["aid"],
        "app_name": SETTINGS["dongchedi"]["params"]["app_name"],
        "city_name": SETTINGS["dongchedi"]["params"]["city_name"],
        "count": 50,
        "offset": 0,
        "rank_data_type": 11,
        "month": datetime.now().strftime("%Y%m"),
        "brand_id": brand_id,
    }
    headers = SETTINGS["dongchedi"]["headers"].copy()

    all_cars = []
    while True:
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            car_list = data.get("data", {}).get("list", [])
            if not car_list:
                break

            for car in car_list:
                car["_brand_name"] = brand_name

            all_cars.extend(car_list)

            if len(car_list) < params["count"]:
                break

            params["offset"] += params["count"]
            time.sleep(SETTINGS["request"]["delay"])

        except Exception as e:
            print(f"# 错误: {e}", file=__import__("sys").stderr)
            break

    return all_cars


def main():
    print("# 开始抓取懂车帝数据...", file=__import__("sys").stderr)
    all_cars = []

    for brand in BRANDS_CONFIG["brands"]:
        if not brand["enabled"] or brand["brand_id"] is None:
            continue

        name = brand["name"]
        bid = brand["brand_id"]
        print(f"# 抓取 {name} (brand_id={bid})...", file=__import__("sys").stderr)

        cars = fetch_cars_by_brand(bid, name)
        all_cars.extend(cars)
        print(f"#   获取到 {len(cars)} 款车型", file=__import__("sys").stderr)
        time.sleep(SETTINGS["request"]["delay"])

    today = datetime.now().strftime("%Y-%m-%d")
    result = {
        "meta": {
            "date": today,
            "source": "dongchedi.com",
            "fetch_time": datetime.now().isoformat(),
            "total_cars": len(all_cars)
        },
        "cars": all_cars
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
