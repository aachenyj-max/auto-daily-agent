"""
使用 Playwright 抓取懂车帝车型详细参数
"""
import json
import time
from pathlib import Path
from datetime import datetime
import sys

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("请先安装 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

PROJECT_ROOT = Path("E:/005.研究生生活/2026/实习/日报agent")

# 需要抓取的参数类别（对应懂车帝参数页面的 tab）
PARAM_CATEGORIES = [
    "基本信息",
    "车身",
    "发动机",
    "电动机",
    "变速箱",
    "底盘/转向",
    "车轮/制动",
    "主动安全",
    "被动安全",
    "辅助/操控配置",
    "外部配置",
    "内部配置",
    "座椅配置",
    "智能互联",
    "影音娱乐",
    "灯光配置",
    "玻璃/后视镜",
    "空调/冰箱",
]


def fetch_car_params(car_id: int, car_name: str, headless: bool = True) -> dict:
    """
    抓取单个车型的详细参数
    car_id: 车型ID（懂车帝的 car_id）
    car_name: 车型名称（用于日志）
    """
    url = f"https://www.dongchedi.com/auto/params-carIds-x-{car_id}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        
        try:
            print(f"  正在访问: {car_name} (ID: {car_id})")
            page.goto(url, timeout=30000, wait_until="networkidle")
            
            # 等待参数表格加载
            page.wait_for_selector("table", timeout=15000)
            
            # 获取所有参数数据
            params_data = {}
            
            # 获取所有参数分类标签
            tabs = page.query_selector_all(".params-tab-item, .tab-item, [class*='tab']")
            
            # 如果没有标签页，直接抓取当前页面的表格
            tables = page.query_selector_all("table")
            
            for table in tables:
                # 获取表格标题（参数类别）
                category = table.query_selector("caption, .table-caption, th")
                category_name = category.inner_text().strip() if category else "未分类"
                
                # 获取表格所有行
                rows = table.query_selector_all("tr")
                category_params = {}
                
                for row in rows[1:]:  # 跳过表头行
                    cells = row.query_selector_all("td, th")
                    if len(cells) >= 2:
                        key = cells[0].inner_text().strip()
                        value = cells[1].inner_text().strip()
                        if key and value:
                            category_params[key] = value
                
                if category_params:
                    params_data[category_name] = category_params
            
            # 如果上面的方法没抓到数据，尝试另一种结构
            if not params_data:
                # 懂车帝的参数页面可能是 div 结构
                param_items = page.query_selector_all("[class*='param-item'], [class*='spec-item']")
                
                current_category = "基本信息"
                for item in param_items:
                    # 判断是否是分类标题
                    category_elem = item.query_selector("[class*='category'], [class*='title']")
                    if category_elem:
                        current_category = category_elem.inner_text().strip()
                        continue
                    
                    # 获取参数名和值
                    key_elem = item.query_selector("[class*='name'], [class*='label']")
                    value_elem = item.query_selector("[class*='value'], [class*='content']")
                    
                    if key_elem and value_elem:
                        key = key_elem.inner_text().strip()
                        value = value_elem.inner_text().strip()
                        if current_category not in params_data:
                            params_data[current_category] = {}
                        params_data[current_category][key] = value
            
            browser.close()
            
            if params_data:
                print(f"  ✓ 成功抓取 {len(params_data)} 个参数类别")
                return params_data
            else:
                print(f"  ✗ 未找到参数数据（页面结构可能已变化）")
                return {}
                
        except PlaywrightTimeout:
            print(f"  ✗ 页面加载超时")
            browser.close()
            return {}
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            browser.close()
            return {}


def fetch_car_params_v2(car_id: int, car_name: str, headless: bool = True) -> dict:
    """
    改进版：通过 JavaScript 注入获取页面数据
    懂车帝的参数页面数据可能在 window.__INITIAL_STATE__ 或类似全局变量中
    """
    url = f"https://www.dongchedi.com/auto/params-carIds-x-{car_id}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        
        try:
            print(f"  正在访问: {car_name} (ID: {car_id})")
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            # 等待页面加载
            time.sleep(3)
            
            # 尝试从页面的 window 对象中获取数据
            # 懂车帝可能使用 React/Vue，数据存储在全局状态中
            params_data = page.evaluate("""
                () => {
                    const result = {};
                    
                    // 方法1: 查找页面上所有表格数据
                    const tables = document.querySelectorAll('table');
                    tables.forEach(table => {
                        const caption = table.querySelector('caption');
                        const category = caption ? caption.innerText.trim() : '未分类';
                        const rows = table.querySelectorAll('tr');
                        const params = {};
                        
                        rows.forEach((row, idx) => {
                            if (idx === 0) return; // 跳过表头
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const key = cells[0].innerText.trim();
                                const value = cells[1].innerText.trim();
                                if (key) params[key] = value;
                            }
                        });
                        
                        if (Object.keys(params).length > 0) {
                            result[category] = params;
                        }
                    });
                    
                    // 方法2: 如果表格没数据，查找 div 结构
                    if (Object.keys(result).length === 0) {
                        const paramSections = document.querySelectorAll('[class*="param-section"], [class*="spec-section"]');
                        paramSections.forEach(section => {
                            const titleElem = section.querySelector('[class*="title"], h3, h4');
                            const category = titleElem ? titleElem.innerText.trim() : '未分类';
                            const params = {};
                            
                            const items = section.querySelectorAll('[class*="item"]');
                            items.forEach(item => {
                                const nameElem = item.querySelector('[class*="name"], [class*="label"]');
                                const valueElem = item.querySelector('[class*="value"], [class*="content"]');
                                if (nameElem && valueElem) {
                                    params[nameElem.innerText.trim()] = valueElem.innerText.trim();
                                }
                            });
                            
                            if (Object.keys(params).length > 0) {
                                result[category] = params;
                            }
                        });
                    }
                    
                    return result;
                }
            """)
            
            browser.close()
            
            if params_data and any(params_data.values()):
                total_params = sum(len(v) for v in params_data.values())
                print(f"  ✓ 成功抓取 {len(params_data)} 个类别，共 {total_params} 个参数")
                return params_data
            else:
                print(f"  ✗ 未找到参数数据")
                return {}
                
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            browser.close()
            return {}


def batch_fetch_params(car_list: list, headless: bool = True, delay: float = 2.0) -> dict:
    """
    批量抓取车型参数
    car_list: [{"car_id": 123, "car_name": "xxx"}, ...]
    """
    results = {}
    
    total = len(car_list)
    for i, car in enumerate(car_list, 1):
        car_id = car.get("car_id")
        car_name = car.get("car_name", f"车型{car_id}")
        
        print(f"\n[{i}/{total}] 抓取: {car_name}")
        
        if not car_id:
            print("  ✗ 缺少 car_id，跳过")
            continue
        
        params = fetch_car_params_v2(car_id, car_name, headless)
        
        if params:
            results[car_id] = {
                "car_name": car_name,
                "car_id": car_id,
                "params": params,
            }
        
        # 延迟，避免被封
        if i < total:
            time.sleep(delay)
    
    return results


def load_car_list(date: str = None) -> list:
    """从 raw 数据加载车型列表"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    raw_file = PROJECT_ROOT / "data" / "raw" / f"{date}.json"
    
    if not raw_file.exists():
        print(f"原始数据文件不存在: {raw_file}")
        return []
    
    with open(raw_file, encoding="utf-8") as f:
        data = json.load(f)
    
    car_list = []
    for car in data.get("cars", []):
        # 获取第一个 online_car_id 作为 car_id
        online_ids = car.get("online_car_ids", "")
        if online_ids:
            try:
                car_id = int(online_ids.split(",")[0])
                car_list.append({
                    "car_id": car_id,
                    "car_name": car.get("series_name", ""),
                    "series_id": car.get("series_id"),
                    "brand_name": car.get("_brand_name", ""),
                })
            except (ValueError, IndexError):
                pass
    
    return car_list


def save_params(params_data: dict, date: str = None):
    """保存抓取的参数数据"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    output_dir = PROJECT_ROOT / "data" / "params"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{date}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "date": date,
                "source": "dongchedi.com",
                "total_cars": len(params_data),
            },
            "cars": params_data,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n参数数据已保存: {output_file}")
    return output_file


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="抓取懂车帝车型详细参数")
    parser.add_argument("--date", default=None, help="数据日期 (默认今天)")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式 (默认开启)")
    parser.add_argument("--show-browser", action="store_false", dest="headless", help="显示浏览器 (调试用)")
    parser.add_argument("--delay", type=float, default=2.0, help="请求延迟 (秒, 默认2)")
    parser.add_argument("--limit", type=int, default=None, help="限制抓取数量 (测试用)")
    parser.add_argument("--car-ids", help="指定抓取的 car_id (逗号分隔)")
    
    args = parser.parse_args()
    
    if args.car_ids:
        # 直接指定 car_id
        car_list = [{"car_id": int(cid.strip()), "car_name": f"车型{cid.strip()}"} 
                    for cid in args.car_ids.split(",")]
    else:
        # 从 raw 数据加载
        car_list = load_car_list(args.date)
    
    if not car_list:
        print("没有找到可抓取的车型")
        sys.exit(1)
    
    print(f"共找到 {len(car_list)} 个车型")
    
    if args.limit:
        car_list = car_list[:args.limit]
        print(f"限制抓取前 {args.limit} 个")
    
    # 批量抓取
    params_data = batch_fetch_params(car_list, headless=args.headless, delay=args.delay)
    
    # 保存
    if params_data:
        save_params(params_data, args.date or datetime.now().strftime("%Y-%m-%d"))
    else:
        print("\n未抓取到任何参数数据")
