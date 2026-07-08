#!/usr/bin/env python3
"""
数据清洗与结构化脚本
输入: data/raw/YYYY-MM-DD.json
输出: data/processed/YYYY-MM-DD.json
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"


def classify_body_type(series_name):
    """根据车型名称推断车身类型"""
    name = series_name.upper()

    # 一、SUV关键词（优先级最高）
    suv_keywords = [
        "SUV", "越野", "探岳", "途观", "途昂", "途锐", "途岳", "探歌", "探陆",
        "CR-V", "RAV4", "皓影", "冠道", "缤越", "博越", "星越", "豪越",
        "汉兰达", "普拉多", "威兰达", "锋兰达", "楼兰", "奕泽",
        "皇冠陆放", "揽境", "揽巡", "途铠",
        "X1", "X3", "X5", "X7", "IX1", "IX3",
        "Q2L", "Q3", "Q4", "Q5", "Q6", "Q7",
        "GLA", "GLB", "GLC", "GLE", "GLS",
        "UR-V", "XR-V", "HR-V",
        "宋PRO", "宋PLUS", "宋ULTRA", "宋L", "元UP", "元PLUS",
        "唐", "海狮", "海豹",
        "问界M", "理想I", "理想L", "理想ONE",
        "蔚来ES", "蔚来EC",
        "小鹏G", "YU7",
        "哈弗", "长安CS", "瑞虎", "领克",
        "MODEL Y",
        "ID.4", "ID.5", "ID.6", "ID. ERA",
        "逍客", "奇骏", "劲客",
        "护卫舰", "缤智",
        "铂智4X", "威飒", "格瑞维亚",
        "东风本田S7", "广汽本田P7", "猎光E:NS2",
        "日产N6", "日产N7", "日产NX",
    ]

    # 二、MPV关键词
    mpv_keywords = [
        "MPV", "商务车", "奥德赛", "GL8", "嘉际", "传祺M8", "传祺M6",
        "腾势D9", "极氪009", "MEGA", "威霆", "威然", "蔚然",
        "V级", "艾力绅", "赛那", "夏",
        "X9",
    ]

    # 三、轿车关键词（精确匹配，去掉Pro/PLUS/MAX/L等通用后缀）
    sedan_keywords = [
        "轿车", "三厢", "SEDAN",
        "凯美瑞", "雅阁", "天籁", "朗逸", "轩逸", "速腾", "迈腾",
        "帝豪", "星瑞", "艾瑞泽",
        "3系", "5系", "7系", "A3", "A4", "A5", "A6", "A7", "A8",
        "C级", "E级", "S级", "CLA", "CLS",
        "A级",
        "MODEL 3", "MODEL3",
        "小米SU", "蔚来ET", "小鹏P", "小鹏MONA",
        "秦", "海豚", "海鸥", "汉", "驱逐舰",
        "卡罗拉", "雷凌", "亚洲龙",
        "高尔夫", "帕萨特", "宝来", "英仕派", "凌渡", "辉昂",
        "思域", "型格",
        "君威", "君越",
        "雷克萨斯ES", "雷克萨斯LS",
        "ZEEKR 0",
        "ID.3", "ID.7", "E3", "E7", "E9", "E2", "BZ3", "BZ5",
        "铂智3X", "铂智7",
        "TIIDA", "LIFE",
    ]

    for kw in suv_keywords:
        if kw in name:
            return "SUV"
    for kw in mpv_keywords:
        if kw in name:
            return "MPV"
    for kw in sedan_keywords:
        if kw in name:
            return "轿车"

    # 兜底：含数字但无明确关键词的，默认为轿车
    # 实际数据中这种情况很少
    return "未知"


def classify_energy_type(series_name, brand_name):
    """根据车型名称和品牌推断能源类型"""
    name = series_name.upper()
    brand = brand_name.upper()

    # 自主新势力全是新能源
    if any(k in brand for k in ["理想", "蔚来", "小鹏", "问界", "小米"]):
        return "纯电动"

    # 比亚迪全是新能源
    if "比亚迪" in brand:
        if any(k in name for k in ["DM", "DHT"]):
            return "插混/增程"
        else:
            return "纯电动"

    # 关键字判断
    if any(k in name for k in ["EV", "纯电", "电动", "EQS", "EQE", "EQC", "ETRON", "EQ"]):
        return "纯电动"
    elif any(k in name for k in ["DM", "DM-I", "DHT", "混动", "PHEV", "增程", "HEV"]):
        return "插混/增程"
    else:
        return "燃油"


def process(raw_file):
    """处理原始数据"""
    with open(raw_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cars = raw["cars"]
    date = raw["meta"]["date"]

    # 按品牌分组
    brand_map = defaultdict(list)
    for car in cars:
        brand = car.get("_brand_name") or car.get("brand_name", "未知")
        brand_map[brand].append(car)

    # 构建 processed 数据
    brands_list = []
    total_new_energy = 0
    total_sedan = 0
    total_suv = 0
    total_mpv = 0

    for brand_name, brand_cars in brand_map.items():
        models = []
        for car in brand_cars:
            name = car.get("series_name", "未知")
            body = classify_body_type(name)
            energy = classify_energy_type(name, brand_name)

            if energy != "燃油":
                total_new_energy += 1
            if body == "轿车":
                total_sedan += 1
            if body == "SUV":
                total_suv += 1
            if body == "MPV":
                total_mpv += 1

            models.append({
                "name": name,
                "series_id": car.get("series_id"),
                "price_min": car.get("min_price"),
                "price_max": car.get("max_price"),
                "price": car.get("price"),
                "dealer_price": car.get("dealer_price"),
                "has_dealer_price": car.get("has_dealer_price"),
                "sales": car.get("count"),
                "rank": car.get("rank"),
                "last_rank": car.get("last_rank"),
                "body_type": body,
                "energy_type": energy,
                "brand_name": car.get("brand_name", ""),
                "sub_brand_name": car.get("sub_brand_name", ""),
                "car_review_count": car.get("car_review_count", 0),
                "series_pic_count": car.get("series_pic_count", 0),
                "descender_price": car.get("descender_price", 0),
                "online_variants": len(car.get("online_car_ids") or []),
                "image": car.get("image", ""),
            })

        # 按销量排序
        models.sort(key=lambda x: x.get("sales") or 0, reverse=True)

        brands_list.append({
            "name": brand_name,
            "model_count": len(brand_cars),
            "top_model": models[0] if models else None,
            "models": models,
        })

    # 市场概览
    market_summary = {
        "total_models": len(cars),
        "new_energy_count": total_new_energy,
        "sedan_count": total_sedan,
        "suv_count": total_suv,
        "mpv_count": total_mpv,
        "new_energy_ratio": round(total_new_energy / len(cars) * 100, 1) if cars else 0,
    }

    # 销量TOP
    top_selling = sorted(
        [{"name": c.get("series_name"), "brand": c.get("_brand_name"), "sales": c.get("count")} for c in cars],
        key=lambda x: x["sales"] or 0, reverse=True
    )[:10]

    result = {
        "report_date": date,
        "market_summary": market_summary,
        "brands": brands_list,
        "top_selling": top_selling,
    }

    return result


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    raw_file = DATA_RAW / f"{today}.json"

    if not raw_file.exists():
        print(f"原始数据文件不存在: {raw_file}")
        return

    print(f"处理原始数据: {raw_file}")
    processed = process(raw_file)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_file = DATA_PROCESSED / f"{today}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

    print(f"处理完成！输出: {out_file}")
    ms = processed['market_summary']
    print(f"  车型总数: {ms['total_models']}")
    print(f"  新能源占比: {ms['new_energy_ratio']}%")
    print(f"  分类: 轿车{ms['sedan_count']} | SUV{ms['suv_count']} | MPV{ms['mpv_count']}")


if __name__ == "__main__":
    main()
