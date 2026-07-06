#!/usr/bin/env python3
"""
补充数据抓取 + 清洗脚本（car_list API + Cookie 登录抓取）

数据来源（按优先级）：
1. Cookie 登录 → Playwright 渲染参数页 → 获取完整车辆参数
2. car_list API → 获取车系变体列表（公开可用）
3. rank_data API（已有字段扩充）

用法:
    python tools/login.py                     # 先登录，保存 Cookie
    python tools/enrich.py                    # 自动检测 Cookie
    python tools/enrich.py --limit 3          # 限制数量
    python tools/enrich.py --no-articles      # 跳过评测
    python tools/enrich.py --no-cookies       # 仅用公开 API
    python tools/enrich.py --use-playwright   # 强制 Playwright（无 Cookie 大概率失败）

依赖:
    pip install beautifulsoup4 requests lxml pyyaml
    pip install playwright playwright-stealth
    pip install 'markitdown[all]'
"""

import json
import sys
import time
import argparse
import requests
import yaml
import re
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# 路径 & 配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_ENRICHED = PROJECT_ROOT / "data" / "processed" / "enriched"
DATA_RAW_ENRICHED = PROJECT_ROOT / "data" / "raw" / "enriched"
DATA_DIR = PROJECT_ROOT / "data"
COOKIE_FILE = DATA_DIR / "cookies.json"


def load_config():
    with open(CONFIG_DIR / "settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cookies():
    """加载已保存的登录 Cookie"""
    if not COOKIE_FILE.exists():
        return None
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        # 过滤过期 Cookie
        now = time.time()
        valid = [c for c in cookies
                 if c.get("expires", -1) > now or c.get("expires", -1) == -1]
        return valid if valid else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 后端 A：Cookie 登录 + Playwright 参数页抓取（首选）
# ---------------------------------------------------------------------------

def _check_playwright_available():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        from playwright_stealth import Stealth  # noqa: F401
        return True
    except ImportError:
        return False


def fetch_params_with_cookies(series_id, car_name, settings, cookies):
    """
    使用已保存的 Cookie + Playwright 抓取参数页

    要求: 先运行 python tools/login.py 完成登录并保存 Cookie

    返回: {
        "structured": {category: {param_name: param_value}},
        "markdown": str,
        "param_count": int,
    }
    """
    if not _check_playwright_available():
        print("    [Cookie模式] Playwright 不可用")
        return None

    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    ws_config = settings.get("web_scraper", {})
    url_template = ws_config.get(
        "series_params_url",
        "https://www.dongchedi.com/auto/params-carIds-{series_id}",
    )
    url = url_template.replace("{series_id}", str(series_id))

    print(f"    参数页: {url}")

    stealth = Stealth()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        # 注入 Cookie
        context.add_cookies(cookies)

        page = context.new_page()
        stealth.apply_stealth_sync(page)

        try:
            resp = page.goto(url, timeout=30000, wait_until="networkidle")
            time.sleep(3)

            # 检测登录状态
            body_text = page.evaluate(
                '() => document.body ? document.body.innerText : ""'
            )
            if "手机验证码登录" in body_text and "参数" not in body_text[:200]:
                print("    [Cookie模式] Cookie 已过期，需要重新登录")
                print("    运行: python tools/login.py")
                browser.close()
                return None

            # ---- 方案1：提取 HTML 表格 ----
            tables_html = page.evaluate("""
                () => {
                    const tables = document.querySelectorAll('table');
                    if (tables.length === 0) return [];
                    return Array.from(tables).map(t => t.outerHTML);
                }
            """)

            if tables_html and len(tables_html) > 0:
                # 用 BeautifulSoup 解析表格
                from bs4 import BeautifulSoup
                from markitdown import MarkItDown
                import tempfile

                all_params = {}
                for html_table in tables_html:
                    soup = BeautifulSoup(html_table, "lxml")
                    # 尝试从caption或前一行获取分类名
                    category = "参数"
                    caption = soup.find("caption")
                    if caption:
                        category = caption.get_text(strip=True)

                    rows = soup.find_all("tr")
                    params = {}
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            k = cells[0].get_text(strip=True)
                            v = cells[1].get_text(strip=True)
                            if k and v and k != v:
                                params[k] = v
                    if params:
                        all_params[category] = params

                if all_params:
                    total = sum(len(v) for v in all_params.values())

                    # 生成 Markdown
                    md_parts = []
                    for cat, cat_params in all_params.items():
                        md_parts.append(f"### {cat}\n")
                        for k, v in cat_params.items():
                            md_parts.append(f"- **{k}**: {v}")
                        md_parts.append("")

                    print(f"    [Cookie模式] 提取 {len(all_params)} 类 {total} 个参数")
                    browser.close()
                    return {
                        "structured": all_params,
                        "markdown": "\n".join(md_parts),
                        "param_count": total,
                    }

            # ---- 方案2：JS 注入提取（备选）----
            params_data = page.evaluate("""
                () => {
                    const result = {};
                    // 尝试多种选择器
                    const tables = document.querySelectorAll(
                        'table, [class*=param], [class*=config], [class*=spec]'
                    );
                    tables.forEach(el => {
                        let category = '参数';
                        const caption = el.querySelector('caption, thead th');
                        if (caption) category = caption.innerText.trim();

                        const rows = el.querySelectorAll('tr');
                        const params = {};
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td, th');
                            if (cells.length >= 2) {
                                const k = cells[0].innerText.trim();
                                const v = cells[1].innerText.trim();
                                if (k && v && k.length < 50) params[k] = v;
                            }
                        });
                        if (Object.keys(params).length > 0) {
                            result[category] = params;
                        }
                    });
                    return result;
                }
            """)

            if params_data and any(params_data.values()):
                total = sum(len(v) for v in params_data.values())
                md_parts = []
                for cat, cat_params in params_data.items():
                    md_parts.append(f"### {cat}\n")
                    for k, v in cat_params.items():
                        md_parts.append(f"- **{k}**: {v}")
                    md_parts.append("")

                print(f"    [Cookie模式] JS提取 {len(params_data)} 类 {total} 个参数")
                browser.close()
                return {
                    "structured": params_data,
                    "markdown": "\n".join(md_parts),
                    "param_count": total,
                }

            # ---- 方案3：获取可见文本 ----
            visible_text = page.evaluate("""
                () => {
                    const paramsSection = document.querySelector(
                        '[class*=param], [class*=config], [class*=spec], main, article'
                    );
                    if (paramsSection) return paramsSection.innerText.substring(0, 5000);
                    return document.body ? document.body.innerText.substring(0, 5000) : '';
                }
            """)

            print(f"    [Cookie模式] 未找到结构化参数表，获取可见文本 {len(visible_text)} 字符")
            browser.close()

            if visible_text and len(visible_text) > 100:
                return {
                    "structured": {},
                    "markdown": f"## {car_name} 参数信息\n\n{visible_text}",
                    "param_count": len(visible_text.split("\n")),
                }

            return None

        except Exception as e:
            print(f"    [Cookie模式] 错误: {e}")
            browser.close()
            return None


# ---------------------------------------------------------------------------
# 后端 B：car_list API（公开可用）
# ---------------------------------------------------------------------------

def fetch_car_list_api(series_id, settings):
    """
    调用懂车帝 car_list API，获取车系下所有变体（车型）信息
    """
    dc = settings["dongchedi"]
    url = f"{dc['base_url']}{dc['api']['car_list']}"
    params = {
        "aid": dc["params"]["aid"],
        "app_name": dc["params"]["app_name"],
        "series_id": series_id,
    }
    headers = dc.get("headers", {})

    try:
        resp = requests.get(url, params=params, headers=headers,
                           timeout=settings["request"]["timeout"])
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    [car_list API] 请求失败: {e}")
        return None

    tabs = data.get("data", {}).get("tab_list", [])
    all_variants = []
    tab_infos = []

    for tab in tabs:
        tab_key = tab.get("tab_key", "")
        items = tab.get("data", [])
        variants = []

        for item in items:
            info = item.get("info", {})
            if info.get("name"):
                variant = {
                    "name": info.get("name", ""),
                    "car_id": info.get("car_id"),
                    "year": info.get("year"),
                    "guide_price": info.get("official_price", ""),
                    "dealer_price": info.get("dealer_price", ""),
                }
                variants.append(variant)

        all_variants.extend(variants)
        tab_infos.append({"tab": tab_key, "count": len(variants)})

    return {
        "variants": all_variants,
        "tab_infos": tab_infos,
        "total_variants": len(all_variants),
    }


def car_list_to_markdown(car_list_result):
    """将 car_list API 结果格式化为 Markdown"""
    if not car_list_result:
        return "", 0

    variants = car_list_result.get("variants", [])
    tab_infos = car_list_result.get("tab_infos", [])

    parts = [f"## 在售车型 ({len(variants)} 款)\n"]

    for ti in tab_infos:
        tab_name = {"online_all": "在售", "online_2026": "2026款",
                    "offline": "停售"}.get(ti["tab"], ti["tab"])
        parts.append(f"**{tab_name}**: {ti['count']} 款")

    parts.append("")

    seen = set()
    for v in variants:
        name = v.get("name", "")
        if name in seen:
            continue
        seen.add(name)
        # 提取变体名称中的关键信息（续航、驱动等）
        specs = _extract_specs_from_name(name)
        if specs:
            parts.append(f"- {name} ({specs})")
        else:
            parts.append(f"- {name}")

    return "\n".join(parts), len(variants)


def _extract_specs_from_name(variant_name):
    """从变体名称中提取关键规格信息"""
    specs = []

    # 续航
    km_match = re.search(r'(\d{3,4})\s*(KM|km|公里)', variant_name)
    if km_match:
        specs.append(f"续航{km_match.group(1)}km")

    # 驱动形式
    if "四驱" in variant_name:
        specs.append("四驱")
    elif "后驱" in variant_name:
        specs.append("后驱")
    elif "前驱" in variant_name:
        specs.append("前驱")

    # 性能
    if "高性能" in variant_name:
        specs.append("高性能")
    if "性能版" in variant_name:
        specs.append("性能版")
    if "Pro" in variant_name:
        specs.append("Pro")

    # 电池/动力
    if "标准续航" in variant_name:
        specs.append("标准续航")
    if "长续航" in variant_name:
        specs.append("长续航")
    if "超长续航" in variant_name:
        specs.append("超长续航")

    return ", ".join(specs) if specs else ""


# ---------------------------------------------------------------------------
# 后端 C：rank_data 已有字段扩充
# ---------------------------------------------------------------------------

def enrich_from_rankdata(series_id, date):
    """
    从已抓取的 rank_data 中提取更多字段
    """
    raw_file = PROJECT_ROOT / "data" / "raw" / f"{date}.json"
    if not raw_file.exists():
        return {}

    with open(raw_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    for car in raw.get("cars", []):
        if car.get("series_id") == series_id:
            return {
                "brand_name": car.get("brand_name", ""),
                "sub_brand_name": car.get("sub_brand_name", ""),
                "dealer_price": car.get("dealer_price", ""),
                "has_dealer_price": car.get("has_dealer_price"),
                "car_review_count": car.get("car_review_count", 0),
                "series_pic_count": car.get("series_pic_count", 0),
                "score": car.get("score", 0),
                "online_car_ids": car.get("online_car_ids", []),
                "offline_car_ids": car.get("offline_car_ids", []),
                "last_rank": car.get("last_rank"),
                "descender_price": car.get("descender_price", 0),
            }

    return {}


# ---------------------------------------------------------------------------
# 评测文章抓取
# ---------------------------------------------------------------------------

def _get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }


def _html_to_markdown(html_content):
    """HTML -> Markdown 清洗"""
    try:
        from markitdown import MarkItDown
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name
        md = MarkItDown()
        result = md.convert(tmp_path)
        text = result.text_content
        Path(tmp_path).unlink(missing_ok=True)
        return text
    except Exception:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)


def fetch_articles(series_id, series_name, max_articles=3, delay=1.5):
    """抓取车系评测文章"""
    url = f"https://www.dongchedi.com/auto/series/{series_id}"
    print(f"  评测页: {url}")
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"  评测页抓取失败: {e}")
        return []

    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    soup = BeautifulSoup(html, "lxml")
    articles = []
    for a in soup.select("a[href]"):
        href = a["href"]
        full_url = urljoin(url, href)
        text = a.get_text(strip=True)[:60]
        if ("/news/" in href or "/article/" in href) and len(text) > 5:
            articles.append({"title": text, "url": full_url})
        if len(articles) >= max_articles:
            break

    result = []
    for i, art in enumerate(articles, 1):
        print(f"    文章 [{i}/{len(articles)}]: {art['title'][:40]}")
        try:
            art_resp = requests.get(art["url"], headers=_get_headers(), timeout=10)
            art_resp.raise_for_status()
            art_md = _html_to_markdown(art_resp.text)
            result.append({
                "title": art["title"],
                "url": art["url"],
                "markdown": art_md[:5000],
            })
            time.sleep(delay)
        except Exception as e:
            print(f"    文章抓取失败: {e}")

    return result


# ---------------------------------------------------------------------------
# 核心逻辑
# ---------------------------------------------------------------------------

def load_top_series(date, limit=None):
    """从 processed 数据加载销量 TOP 车系列表"""
    processed_file = DATA_PROCESSED / f"{date}.json"
    if not processed_file.exists():
        print(f"错误: 处理后的数据文件不存在: {processed_file}")
        print("请先运行: python tools/scraper.py && python tools/processor.py")
        return []

    with open(processed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    series_list = []
    for item in data.get("top_selling", []):
        series_list.append({
            "name": item.get("name"),
            "brand": item.get("brand"),
            "sales": item.get("sales"),
        })

    # 从 raw 数据补充 series_id
    raw_file = PROJECT_ROOT / "data" / "raw" / f"{date}.json"
    if raw_file.exists():
        with open(raw_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        name_to_sid = {}
        for car in raw.get("cars", []):
            name = car.get("series_name")
            sid = car.get("series_id")
            if name and sid:
                name_to_sid[name] = sid
        for s in series_list:
            s["series_id"] = name_to_sid.get(s["name"])

    series_list = [s for s in series_list if s.get("series_id")]
    if limit:
        series_list = series_list[:limit]
    return series_list


def enrich_one_series(series_id, series_name, settings,
                      use_cookies=True, use_playwright=False, date=None):
    """
    抓取单个车系的补充数据
    优先级: Cookie+Playwright > car_list API > rank_data 扩充
    """
    result = {
        "series_id": series_id,
        "series_name": series_name,
        "variants": [],
        "params": None,
        "backend": "car_list_api",
        "rank_extra": {},
    }

    # 1. 尝试 Cookie + Playwright 参数页抓取
    if use_cookies:
        cookies = load_cookies()
        if cookies and _check_playwright_available():
            params_result = fetch_params_with_cookies(
                series_id, series_name, settings, cookies
            )
            if params_result:
                result["params"] = params_result
                result["backend"] = "cookie_playwright"
                # 仍然获取变体列表作为补充
                car_list_result = fetch_car_list_api(series_id, settings)
                if car_list_result:
                    result["variants"] = car_list_result["variants"]
                    result["variant_count"] = car_list_result["total_variants"]
                    print(f"    [car_list API] 补充 {car_list_result['total_variants']} 个变体")
                return result
            else:
                print("    Cookie 抓取失败，降级到 car_list API")
        elif cookies and not _check_playwright_available():
            print("    Playwright 不可用，使用 car_list API")
        elif not cookies:
            print("    未登录，使用 car_list API")
            print("    提示: 运行 python tools/login.py 登录后可获取完整参数")

    # 2. 强制 Playwright 模式（无 Cookie，大概率失败）
    if use_playwright and _check_playwright_available():
        pw_result = fetch_params_with_cookies(
            series_id, series_name, settings, None
        )
        if pw_result:
            result["params"] = pw_result
            result["backend"] = "playwright"

    # 3. car_list API（兜底）
    car_list_result = fetch_car_list_api(series_id, settings)
    if car_list_result:
        result["variants"] = car_list_result["variants"]
        result["variant_count"] = car_list_result["total_variants"]
        print(f"    [car_list API] 获取 {car_list_result['total_variants']} 个变体")

    # 4. rank_data 扩充字段
    if date:
        result["rank_extra"] = enrich_from_rankdata(series_id, date)

    return result


def run_enrich(date=None, limit=None, no_articles=False,
               use_playwright=False, use_cookies=True):
    """主入口"""
    settings = load_config()

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # 检测 Cookie 状态
    cookies_available = bool(load_cookies())
    if use_cookies and not cookies_available:
        print("提示: 未登录，将仅使用公开 API")
        print("运行 `python tools/login.py` 登录后可获取车系完整参数\n")

    # 后端标签
    if use_cookies and cookies_available:
        backend_label = "Cookie + Playwright + car_list API"
    elif use_playwright:
        backend_label = "Playwright + car_list API"
    else:
        backend_label = "car_list API"

    print("=" * 60)
    print(f"补充数据抓取 - {date}")
    print(f"数据来源: {backend_label}")
    print("=" * 60)

    series_list = load_top_series(date, limit=limit)
    if not series_list:
        print("没有可抓取的车系（请先运行 scraper + processor）")
        return

    ws_config = settings.get("web_scraper", {})
    max_series = ws_config.get("max_series_per_run", 10)
    if not limit:
        series_list = series_list[:max_series]

    print(f"共 {len(series_list)} 个车系待补充\n")

    DATA_RAW_ENRICHED.mkdir(parents=True, exist_ok=True)
    DATA_ENRICHED.mkdir(parents=True, exist_ok=True)

    all_enriched = []
    total_variants = 0
    total_params = 0

    for i, series in enumerate(series_list, 1):
        sid = series["series_id"]
        name = series["name"]
        print(f"[{i}/{len(series_list)}] {name} (series_id={sid})")

        enriched = enrich_one_series(
            sid, name, settings,
            use_cookies=use_cookies,
            use_playwright=use_playwright,
            date=date,
        )
        enriched["brand"] = series.get("brand")
        enriched["sales"] = series.get("sales")
        enriched["articles"] = []

        total_variants += enriched.get("variant_count", 0)
        if enriched.get("params"):
            total_params += enriched["params"].get("param_count", 0)

        # 保存变体 Markdown
        if enriched.get("variants"):
            md_text, _ = car_list_to_markdown(
                {"variants": enriched["variants"],
                 "tab_infos": [], "total_variants": enriched["variant_count"]}
            )
            md_file = DATA_RAW_ENRICHED / f"{date}_variants_{sid}.md"
            md_file.write_text(
                f"# {name} - 车型变体\n\n{md_text}\n", encoding="utf-8"
            )

        # 保存参数 Markdown
        if enriched.get("params") and enriched["params"].get("markdown"):
            param_file = DATA_RAW_ENRICHED / f"{date}_params_{sid}.md"
            param_file.write_text(
                f"# {name} - 车辆参数\n\n{enriched['params']['markdown']}\n",
                encoding="utf-8",
            )

        time.sleep(settings["request"]["delay"] * 0.5)

        # 抓评测文章
        if not no_articles:
            articles = fetch_articles(sid, name, max_articles=3,
                                      delay=settings["request"]["delay"])
            enriched["articles"] = articles
            if articles:
                art_file = DATA_RAW_ENRICHED / f"{date}_articles_{sid}.md"
                parts = [f"# {name} - 评测文章\n"]
                for art in articles:
                    parts.append(f"## {art['title']}\n\n{art['markdown']}\n")
                art_file.write_text("\n".join(parts), encoding="utf-8")

        all_enriched.append(enriched)
        print()

        if i < len(series_list):
            time.sleep(settings["request"]["delay"])

    # 保存汇总
    summary_file = DATA_ENRICHED / f"{date}.json"
    result = {
        "meta": {
            "date": date,
            "source": "dongchedi.com",
            "backend": backend_label,
            "fetch_time": datetime.now().isoformat(),
            "total_series": len(all_enriched),
            "total_variants": total_variants,
            "total_params": total_params,
            "tools": ["car_list_api", "playwright", "markitdown", "cookie_auth"],
        },
        "series": all_enriched,
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("补充数据抓取完成！")
    print(f"  车系数: {len(all_enriched)}")
    print(f"  总变体数: {total_variants}")
    print(f"  总参数数: {total_params}")
    print(f"  汇总文件: {summary_file}")
    print(f"  原始数据: {DATA_RAW_ENRICHED}/")
    print("=" * 60)

    return summary_file


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="补充数据抓取（Cookie登录 + car_list API）"
    )
    parser.add_argument("--date", default=None, help="数据日期")
    parser.add_argument("--limit", type=int, default=None, help="限制车系数量")
    parser.add_argument("--no-articles", action="store_true", help="跳过评测文章")
    parser.add_argument("--no-cookies", action="store_true",
                        help="不使用 Cookie（仅公开 API）")
    parser.add_argument("--use-playwright", action="store_true",
                        help="强制 Playwright（无 Cookie 大概率失败）")
    args = parser.parse_args()

    run_enrich(
        date=args.date,
        limit=args.limit,
        no_articles=args.no_articles,
        use_playwright=args.use_playwright,
        use_cookies=not args.no_cookies,
    )
