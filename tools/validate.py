#!/usr/bin/env python3
"""
验证脚本：检查数据抓取和处理结果
用法: python tools/validate.py --date 2026-07-02
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"


def validate_raw_data(date):
    """验证原始数据"""
    raw_file = DATA_RAW / f"{date}.json"
    if not raw_file.exists():
        return False, f"原始数据文件不存在: {raw_file}"

    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cars = data.get("cars", [])
    meta = data.get("meta", {})

    errors = []
    if meta.get("total_cars", 0) == 0:
        errors.append("没有抓取到任何车型数据")
    if len(cars) < 10:
        errors.append(f"车型数量过少: {len(cars)}")

    # 检查必需字段
    required_fields = ["series_id", "series_name", "brand_id", "min_price", "max_price"]
    for i, car in enumerate(cars[:5]):
        for field in required_fields:
            if field not in car:
                errors.append(f"车型 #{i} 缺少字段: {field}")

    return len(errors) == 0, errors


def validate_processed_data(date):
    """验证结构化数据"""
    proc_file = DATA_PROCESSED / f"{date}.json"
    if not proc_file.exists():
        return False, f"结构化数据文件不存在: {proc_file}"

    with open(proc_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    if not data.get("report_date"):
        errors.append("缺少 report_date")
    if not data.get("brands"):
        errors.append("缺少 brands 数据")
    if data.get("market_summary", {}).get("total_models", 0) == 0:
        errors.append("market_summary.total_models 为 0")

    return len(errors) == 0, errors


def validate_report(date):
    """验证日报文件"""
    report_file = OUTPUT_DIR / f"{date}.md"
    if not report_file.exists():
        return False, f"日报文件不存在: {report_file}"

    with open(report_file, "r", encoding="utf-8") as f:
        content = f.read()

    errors = []
    required_sections = ["市场概览", "品牌动态", "车型推荐", "购买建议"]
    for section in required_sections:
        if section not in content:
            errors.append(f"日报缺少章节: {section}")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    print(f"验证日期: {args.date}")
    print("=" * 50)

    results = []

    # 验证原始数据
    ok, msg = validate_raw_data(args.date)
    status = "[OK] 通过" if ok else "[FAIL] 失败"
    print(f"[1/3] 原始数据: {status}")
    if not ok:
        for e in msg:
            print(f"      - {e}")
    results.append(ok)

    # 验证结构化数据
    ok, msg = validate_processed_data(args.date)
    status = "[OK] 通过" if ok else "[FAIL] 失败"
    print(f"[2/3] 结构化数据: {status}")
    if not ok:
        for e in msg:
            print(f"      - {e}")
    results.append(ok)

    # 验证日报
    ok, msg = validate_report(args.date)
    status = "[OK] 通过" if ok else "[FAIL] 失败（可能尚未生成）"
    print(f"[3/3] 日报文件: {status}")
    if not ok:
        for e in msg:
            print(f"      - {e}")
    results.append(ok)

    print("=" * 50)
    passed = sum(results)
    print(f"验证结果: {passed}/3 通过")

    # 保存验证日志
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"validate-{args.date}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"验证日期: {args.date}\n")
        f.write(f"结果: {passed}/3 通过\n")


if __name__ == "__main__":
    main()
