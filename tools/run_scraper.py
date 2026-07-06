#!/usr/bin/env python3
"""
懂车帝数据抓取 + 保存脚本
用法: python tools/run_scraper.py
输出: data/raw/YYYY-MM-DD.json
"""

import json
import time
import requests
import yaml
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
CONFIG_DIR = PROJECT_ROOT / "config"

# 加载配置（显式指定 UTF-8）
with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)
with open(CONFIG_DIR / "brands.json", "r", encoding="utf-8") as f:
    BRANDS_CONFIG = json.load(f)


def fetch_cars(brand_id):
    """抓取单个品牌的车型数据"""
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
            all_cars.extend(car_list)
            if len(car_list) < params["count"]:
                break
            params["offset"] += params["count"]
            time.sleep(SETTINGS["request"]["delay"])
        except Exception as e:
            print(f"  错误: {e}")
            break

    return all_cars


def main():
    print(f"开始抓取 - {datetime.now().strftime('%H:%M:%S')}")
    all_cars = []

    for brand in BRANDS_CONFIG["brands"]:
        if not brand["enabled"] or brand["brand_id"] is None:
            continue
        name = brand["name"]
        bid = brand["brand_id"]
        print(f"  抓取 {name}...", end=" ")
        cars = fetch_cars(bid)
        for c in cars:
            c["_brand_name"] = name
        all_cars.extend(cars)
        print(f"获取到 {len(cars)} 款")
        time.sleep(SETTINGS["request"]["delay"])

    today = datetime.now().strftime("%Y-%m-%d")
    result = {
        "meta": {
            "date": today,
            "source": "dongchedi.com",
            "fetch_time": datetime.now().isoformat(),
            "total_cars": len(all_cars),
        },
        "cars": all_cars,
    }

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out_file = DATA_RAW / f"{today}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共 {len(all_cars)} 款车型")
    print(f"保存至: {out_file}")


if __name__ == "__main__":
    main()
