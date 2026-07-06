#!/usr/bin/env python3
"""
获取懂车帝品牌 ID 映射脚本
用法: python tools/fetch_brand_ids.py
输出: 更新 config/brands.json
"""

import json
import requests
import yaml
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

with open(CONFIG_DIR / "brands.json", "r", encoding="utf-8") as f:
    BRANDS_CONFIG = json.load(f)


def fetch_all_brands():
    """从懂车帝 API 获取所有品牌映射"""
    url = f"{SETTINGS['dongchedi']['base_url']}{SETTINGS['dongchedi']['api']['rank_data']}"
    params = {
        "aid": SETTINGS["dongchedi"]["params"]["aid"],
        "app_name": SETTINGS["dongchedi"]["params"]["app_name"],
        "city_name": SETTINGS["dongchedi"]["params"]["city_name"],
        "count": 50,
        "offset": 0,
        "rank_data_type": 11,
        "month": datetime.now().strftime("%Y%m"),
    }
    headers = SETTINGS["dongchedi"]["headers"].copy()

    brand_map = {}  # {brand_name: brand_id}

    print("正在获取品牌映射...")
    while True:
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            car_list = data.get("data", {}).get("list", [])

            if not car_list:
                break

            for car in car_list:
                brand_name = car.get("brand_name", "")
                brand_id = car.get("brand_id")
                if brand_name and brand_id and brand_name not in brand_map:
                    brand_map[brand_name] = brand_id

            if len(car_list) < params["count"]:
                break

            params["offset"] += params["count"]
            import time
            time.sleep(SETTINGS["request"]["delay"])

        except Exception as e:
            print(f"抓取失败: {e}")
            break

    return brand_map


def update_brands_config(brand_map):
    """更新 brands.json 配置"""
    updated = 0
    for brand in BRANDS_CONFIG["brands"]:
        name = brand["name"]
        # 尝试精确匹配
        if name in brand_map:
            brand["brand_id"] = brand_map[name]
            print(f"  [OK] {name}: brand_id = {brand_map[name]}")
            updated += 1
        else:
            # 尝试模糊匹配
            matched = False
            for bn, bid in brand_map.items():
                if name in bn or bn in name:
                    brand["brand_id"] = bid
                    print(f"  [OK] {name} (匹配到 {bn}): brand_id = {bid}")
                    updated += 1
                    matched = True
                    break
            if not matched:
                print(f"  [FAIL] {name}: 未找到对应的 brand_id")

    BRANDS_CONFIG["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    with open(CONFIG_DIR / "brands.json", "w", encoding="utf-8") as f:
        json.dump(BRANDS_CONFIG, f, ensure_ascii=False, indent=2)

    print(f"\n已更新 {updated}/{len(BRANDS_CONFIG['brands'])} 个品牌的 brand_id")
    print(f"配置文件已保存: {CONFIG_DIR / 'brands.json'}")


if __name__ == "__main__":
    brand_map = fetch_all_brands()
    print(f"共获取 {len(brand_map)} 个品牌")
    update_brands_config(brand_map)
