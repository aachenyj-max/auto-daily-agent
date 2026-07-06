#!/usr/bin/env python3
"""
懂车帝车型数据抓取脚本
用法: python tools/scraper.py
输出: data/raw/YYYY-MM-DD.json
"""

import json
import time
import os
import sys
import requests
import yaml
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
CONFIG_DIR = PROJECT_ROOT / "config"

# 加载配置
with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

with open(CONFIG_DIR / "brands.json", "r", encoding="utf-8") as f:
    BRANDS_CONFIG = json.load(f)


def get_headers():
    """获取请求头"""
    return SETTINGS["dongchedi"]["headers"].copy()


def fetch_brand_list():
    """
    获取懂车帝品牌列表
    通过解析车型库页面获取品牌 ID 和名称的映射
    """
    print("正在获取品牌列表...")
    url = f"{SETTINGS['dongchedi']['base_url']}/auto/library"
    headers = get_headers()
    headers["Accept"] = "text/html,application/xhtml+xml"

    try:
        resp = requests.get(url, headers=headers, timeout=SETTINGS["request"]["timeout"])
        resp.raise_for_status()

        # 从页面中提取品牌列表（通过解析 JavaScript 变量或 API）
        # 实际上，懂车帝的品牌列表可以通过一个内部 API 获取
        # 这里我们尝试调用一个已知的接口

        # 方法：通过搜索接口获取品牌列表
        brands = []
        for brand_info in BRANDS_CONFIG["brands"]:
            brand_name = brand_info["name"]
            # 尝试通过搜索获取品牌 ID
            search_url = f"{SETTINGS['dongchedi']['base_url']}/search"
            params = {
                "keyword": brand_name,
                "currTab": 1,
                "city_name": SETTINGS["dongchedi"]["params"]["city_name"]
            }
            # 这个搜索接口返回的是网页，不是 API
            # 所以我们需要另一种方法

            # 实际上，懂车帝有一个内部 API 可以获取品牌列表
            # 让我们尝试调用 /motor/pc/car/brand_list 或类似的接口

            print(f"  品牌 {brand_name}: 需要手动配置 brand_id")
            brands.append({"name": brand_name, "brand_id": None})

        return brands

    except Exception as e:
        print(f"获取品牌列表失败: {e}")
        return []


def fetch_car_rank_data(brand_id=None, new_energy_type=None, body_type=None):
    """
    获取车型排行数据
    API: /motor/pc/car/rank_data
    """
    url = f"{SETTINGS['dongchedi']['base_url']}{SETTINGS['dongchedi']['api']['rank_data']}"
    params = {
        "aid": SETTINGS["dongchedi"]["params"]["aid"],
        "app_name": SETTINGS["dongchedi"]["params"]["app_name"],
        "city_name": SETTINGS["dongchedi"]["params"]["city_name"],
        "count": 50,
        "offset": 0,
        "rank_data_type": 11,  # 销量排行
        "month": datetime.now().strftime("%Y%m"),  # 当前月份
    }

    if brand_id:
        params["brand_id"] = brand_id
    if new_energy_type:
        params["new_energy_type"] = new_energy_type

    headers = get_headers()

    all_cars = []
    while True:
        try:
            resp = requests.get(url, params=params, headers=headers,
                               timeout=SETTINGS["request"]["timeout"])
            resp.raise_for_status()
            data = resp.json()

            # 懂车帝 API 返回格式：{data: {list: [...]}}
            car_list = data.get("data", {}).get("list", [])
            if not car_list:
                # 尝试其他可能的路径
                car_list = data.get("data", [])
                if not isinstance(car_list, list):
                    car_list = []
            if not car_list:
                break

            all_cars.extend(car_list)

            # 检查是否还有更多数据
            if len(car_list) < params["count"]:
                break

            params["offset"] += params["count"]
            time.sleep(SETTINGS["request"]["delay"])

        except Exception as e:
            print(f"  抓取失败: {e}")
            break

    return all_cars


def fetch_series_detail(series_id):
    """
    获取车系详情
    API: /motor/pc/car/series/detail
    """
    url = f"{SETTINGS['dongchedi']['base_url']}{SETTINGS['dongchedi']['api']['car_detail']}"
    params = {
        "aid": SETTINGS["dongchedi"]["params"]["aid"],
        "app_name": SETTINGS["dongchedi"]["params"]["app_name"],
        "series_id": series_id,
    }
    headers = get_headers()

    try:
        resp = requests.get(url, params=params, headers=headers,
                           timeout=SETTINGS["request"]["timeout"])
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {})
    except Exception as e:
        print(f"  获取车系详情失败 (series_id={series_id}): {e}")
        return {}


def scrape_dongchedi():
    """
    主抓取函数
    """
    print(f"开始抓取懂车帝数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_cars = []

    # 遍历目标品牌
    fetch_details = "--with-details" in sys.argv

    for brand_info in BRANDS_CONFIG["brands"]:
        if not brand_info["enabled"]:
            continue

        brand_name = brand_info["name"]
        brand_id = brand_info["brand_id"]

        print(f"\n正在抓取品牌: {brand_name} (brand_id={brand_id})")

        if brand_id is None:
            print(f"  警告: {brand_name} 的 brand_id 未配置，跳过")
            continue

        # 抓取该品牌的车型数据
        cars = fetch_car_rank_data(brand_id=brand_id)

        # 补充车系详情（可选）
        if fetch_details:
            for car in cars:
                series_id = car.get("series_id")
                if series_id:
                    print(f"  获取详情: {car.get('series_name', '未知')}")
                    detail = fetch_series_detail(series_id)
                    car["detail"] = detail
                    time.sleep(SETTINGS["request"]["delay"])

        all_cars.extend(cars)
        time.sleep(SETTINGS["request"]["delay"])

    # 保存原始数据
    today = datetime.now().strftime("%Y-%m-%d")
    output_file = DATA_RAW_DIR / f"{today}.json"

    result = {
        "meta": {
            "date": today,
            "source": "dongchedi.com",
            "fetch_time": datetime.now().isoformat(),
            "total_cars": len(all_cars)
        },
        "cars": all_cars
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n抓取完成！共获取 {len(all_cars)} 款车型")
    print(f"数据已保存至: {output_file}")

    return output_file


if __name__ == "__main__":
    # 创建输出目录
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 执行抓取
    scrape_dongchedi()
