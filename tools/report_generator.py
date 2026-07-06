#!/usr/bin/env python3
"""
日报生成脚本
输入: data/processed/YYYY-MM-DD.json + (可选)data/processed/enriched/YYYY-MM-DD.json + config/report_prompt.txt
输出: output/YYYY-MM-DD.md
用法: python tools/report_generator.py --date 2026-07-02 --api-key YOUR_KEY --api-base URL --model MODEL
"""

import argparse
import json
import os
import requests
import yaml
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_ENRICHED = PROJECT_ROOT / "data" / "processed" / "enriched"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_config():
    """加载配置"""
    with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompt():
    """加载提示词"""
    with open(CONFIG_DIR / "report_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def load_processed_data(date):
    """加载结构化数据"""
    file = DATA_PROCESSED / f"{date}.json"
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_enriched_data(date):
    """加载补充管线数据（web-scraper + markitdown 产出），可选"""
    file = DATA_ENRICHED / f"{date}.json"
    if not file.exists():
        return None
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def build_enriched_context(enriched_data, max_series=5):
    """将补充数据转为 LLM 可消费的 Markdown 上下文摘要"""
    if not enriched_data:
        return ""

    sections = []
    for series in enriched_data.get("series", [])[:max_series]:
        name = series.get("series_name", "未知")
        parts = [f"### {name}\n"]

        backend = series.get("backend", "unknown")
        variant_count = series.get("variant_count", 0)
        parts.append(f"*来源: {backend} | 变体数: {variant_count}*\n")

        # 优先：Playwright 渲染的结构化参数
        params = series.get("params")
        if params and params.get("structured"):
            structured = params.get("structured", {})
            param_count = params.get("param_count", 0)
            parts.append(f"**关键参数 ({param_count} 项):**\n")
            key_categories = [
                "基本信息", "车身", "发动机", "电动机",
                "变速箱", "底盘/转向", "车轮/制动",
                "主/被动安全", "辅助/操控配置",
                "内部配置", "座椅配置",
                "智能驾驶", "续航", "充电",
            ]
            for cat_name, cat_params in structured.items():
                if any(kw in cat_name for kw in key_categories):
                    items = list(cat_params.items())[:8]
                    items_str = "; ".join(f"{k}={v}" for k, v in items)
                    parts.append(f"  - {cat_name}: {items_str}")
            parts.append("")

        # 其次：car_list API 变体列表
        variants = series.get("variants", [])
        if variants:
            parts.append(f"**在售车型 ({len(variants)} 款):**")
            for v in variants[:15]:  # 最多 15 个
                parts.append(f"- {v.get('name', '')}")
            parts.append("")

        # 评测摘要
        articles = series.get("articles", [])
        for art in articles[:2]:
            title = art.get("title", "评测")
            md = art.get("markdown", "")[:800]
            parts.append(f"**评测: {title}**\n{md}\n")

        sections.append("\n".join(parts))

    return "\n\n---\n\n".join(sections)


def call_llm_api(prompt, data, enriched_context, api_key, api_base, model):
    """调用 LLM API 生成日报"""
    # 构造完整提示词：基础数据 + 补充上下文
    full_prompt = f"{prompt}\n\n## 输入数据\n\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n"

    # 如果有补充数据，追加到提示词
    if enriched_context:
        full_prompt += f"\n## 补充数据（来自 HTML 抓取 + markitdown 清洗）\n\n{enriched_context}\n"

    # 使用 OpenAI 兼容 API 格式
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位专业的汽车行业分析师。"},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4000,
    }

    # 如果 api_base 指定了，使用指定的 base URL
    if api_base:
        url = f"{api_base}/chat/completions"
    else:
        url = "https://api.openai.com/v1/chat/completions"

    resp = None
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM API 调用失败: {e}")
        if resp is not None:
            print(f"API 响应: {resp.text[:500]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="生成汽车日报")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="数据日期")
    parser.add_argument("--api-key", help="LLM API Key（也可在 config/settings.yaml 中配置）")
    parser.add_argument("--api-base", help="LLM API Base URL")
    parser.add_argument("--model", help="LLM 模型名称")
    args = parser.parse_args()

    # 加载配置
    settings = load_config()
    api_key = args.api_key or os.getenv("LLM_API_KEY") or settings.get("llm", {}).get("api_key")
    api_base = args.api_base or os.getenv("LLM_API_BASE") or settings.get("llm", {}).get("api_base")
    model = args.model or os.getenv("LLM_MODEL") or settings.get("llm", {}).get("model")

    if not api_key:
        print("错误: 未配置 LLM API Key")
        print("请使用 LLM_API_KEY 环境变量，或使用 --api-key 参数")
        return

    print(f"生成日报 - 日期: {args.date}")
    print(f"模型: {model or '使用默认'}")

    # 加载提示词和数据
    prompt = load_prompt()
    data = load_processed_data(args.date)

    # 加载补充数据（可选）
    enriched_data = load_enriched_data(args.date)
    enriched_context = ""
    if enriched_data:
        print(f"发现补充数据: {len(enriched_data.get('series', []))} 个车系详情")
        enriched_context = build_enriched_context(enriched_data)
    else:
        print("无补充数据（如需丰富日报，请先运行: python tools/enrich.py）")

    # 调用 LLM API
    print("正在调用 LLM API 生成日报...")
    report = call_llm_api(prompt, data, enriched_context, api_key, api_base, model)

    if not report:
        print("日报生成失败")
        return

    # 保存日报
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"{args.date}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"日报生成成功！保存至: {out_file}")


if __name__ == "__main__":
    main()
