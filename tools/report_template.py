#!/usr/bin/env python3
"""
模板版日报生成器（不依赖 LLM API）
用法: python tools/report_template.py --date 2026-07-02
输出: output/YYYY-MM-DD.md
"""

import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_data(date):
    with open(DATA_PROCESSED / f"{date}.json", "r", encoding="utf-8") as f:
        return json.load(f)


def generate_report(data):
    """根据模板生成日报"""
    date = data["report_date"]
    ms = data["market_summary"]
    brands = data["brands"]
    top_selling = data["top_selling"]

    lines = []
    lines.append(f"# 汽车市场日报 - {date}")
    lines.append("")
    lines.append("> 数据来源：懂车帝（dongchedi.com）| 由汽车日报 Agent 自动生成")
    lines.append("")

    # 一、市场概览
    lines.append("## 一、市场概览")
    lines.append("")
    lines.append(f"- **监测车型总数**：{ms['total_models']} 款")
    lines.append(f"- **新能源车型**：{ms['new_energy_count']} 款，占比 {ms['new_energy_ratio']}%")
    lines.append(f"- **轿车**：{ms.get('sedan_count', 0)} 款 | **SUV**：{ms.get('suv_count', 0)} 款 | **MPV**：{ms.get('mpv_count', 0)} 款")
    lines.append("")
    lines.append("### 销量 TOP 5")
    lines.append("")
    lines.append("| 排名 | 车型 | 品牌 | 月销量 |")
    lines.append("|------|------|------|--------|")
    for i, car in enumerate(top_selling[:5], 1):
        lines.append(f"| {i} | {car['name']} | {car['brand']} | {car['sales']:,} |")
    lines.append("")

    # 二、品牌动态
    lines.append("## 二、品牌动态")
    lines.append("")
    for brand in brands:
        name = brand["name"]
        count = brand["model_count"]
        top = brand.get("top_model")
        lines.append(f"### {name}（{count} 款车型）")
        lines.append("")
        if top:
            lines.append(f"- **主力车型**：{top['name']}")
            lines.append(f"- **价格区间**：{top['price']}")
            lines.append(f"- **月销量**：{top.get('sales', 'N/A'):,}")
        lines.append("")

    # 三、重点车型推荐
    lines.append("## 三、重点车型推荐")
    lines.append("")

    # 按价格区间分类
    cheap = []  # <15万
    mid = []    # 15-25万
    exp = []    # >25万

    for brand in brands:
        for m in brand.get("models", []):
            price_avg = (m.get("price_min", 0) + m.get("price_max", 0)) / 2
            if price_avg < 15:
                cheap.append((brand["name"], m))
            elif price_avg < 25:
                mid.append((brand["name"], m))
            else:
                exp.append((brand["name"], m))

    lines.append("### 1. 性价比之王（15万以下）")
    lines.append("")
    for brand_name, m in cheap[:3]:
        lines.append(f"**{m['name']}（{brand_name}）**")
        lines.append(f"- 价格：{m['price']}")
        lines.append(f"- 销量：{m.get('sales', 'N/A'):,}/月")
        lines.append(f"- 推荐理由：销量排名靠前，性价比高")
        lines.append("")

    lines.append("### 2. 家庭首选（15-25万）")
    lines.append("")
    for brand_name, m in mid[:3]:
        lines.append(f"**{m['name']}（{brand_name}）**")
        lines.append(f"- 价格：{m['price']}")
        lines.append(f"- 销量：{m.get('sales', 'N/A'):,}/月")
        lines.append("")

    lines.append("### 3. 豪华之选（25万以上）")
    lines.append("")
    for brand_name, m in exp[:3]:
        lines.append(f"**{m['name']}（{brand_name}）**")
        lines.append(f"- 价格：{m['price']}")
        lines.append(f"- 销量：{m.get('sales', 'N/A'):,}/月")
        lines.append("")

    # 四、购买建议
    lines.append("## 四、购买建议")
    lines.append("")
    lines.append("### 当前是否是购车好时机？")
    lines.append("")
    lines.append("根据本月数据，新能源车型占比持续提升，主流品牌价格竞争加剧，")
    lines.append("部分车型有优惠空间。如近期有购车计划，建议：")
    lines.append("1. 关注月底经销商冲量优惠")
    lines.append("2. 新能源车型可关注地方补贴政策")
    lines.append("3. 燃油车建议等年底清库存时入手")
    lines.append("")
    lines.append("### 不同需求推荐")
    lines.append("")
    lines.append("- **通勤代步**：推荐纯电车型，使用成本低")
    lines.append("- **家庭用车**：推荐插混/增程，无续航焦虑")
    lines.append("- **商务接待**：推荐豪华品牌燃油车或高端新能源")
    lines.append("")
    lines.append("### 注意事项")
    lines.append("")
    lines.append("- 以上价格为懂车帝指导价，实际成交价可能有优惠")
    lines.append("- 新能源车请确认家中/单位是否有充电条件")
    lines.append("- 提车前建议试驾，关注实际空间和舒适性")
    lines.append("")
    lines.append("---")
    lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*由汽车日报 Agent 自动生成，数据仅供参考*")

    return "\n".join(lines)


def main():
    date = datetime.now().strftime("%Y-%m-%d")
    print(f"生成模板日报 - {date}")

    data = load_data(date)
    report = generate_report(data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"{date}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"日报已生成：{out_file}")


if __name__ == "__main__":
    main()
