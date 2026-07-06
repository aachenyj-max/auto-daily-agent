#!/usr/bin/env python3
"""
懂车帝登录/登出工具

通过 Playwright 自动化登录流程：
1. 打开懂车帝首页 → 点击登录按钮
2. 用户输入手机号 → 点击发送验证码
3. 用户手动输入验证码 → 完成登录
4. 保存 Cookie 到文件供 enrich.py 使用
5. 支持登出（删除 Cookie 文件）

用法:
    python tools/login.py                      # 交互式登录
    python tools/login.py --phone 13800138000  # 指定手机号
    python tools/login.py --logout             # 登出（清除 Cookie）

依赖: playwright, playwright-stealth
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COOKIE_FILE = DATA_DIR / "cookies.json"
SESSION_FILE = DATA_DIR / "session_info.json"


def _create_browser_context(headless=False):
    """创建 stealth 模式浏览器上下文"""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    stealth = Stealth()
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
    )
    page = context.new_page()
    stealth.apply_stealth_sync(page)
    return p, browser, context, page


def login(phone=None, headless=False):
    """
    执行登录流程，保存 Cookie

    Args:
        phone: 手机号（None 则交互式输入）
        headless: 是否无头模式（False 则显示浏览器窗口）
    """
    print("=" * 60)
    print("懂车帝登录工具")
    print("=" * 60)

    # 检查依赖
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
    except ImportError as e:
        print(f"缺少依赖: {e}")
        print("请运行: pip install playwright playwright-stealth")
        print("       playwright install chromium")
        return None

    # 获取手机号
    if not phone:
        phone = input("\n请输入手机号: ").strip()
        if not phone or len(phone) != 11:
            print("手机号格式不正确（需要11位数字）")
            return None

    print(f"\n[1/4] 打开懂车帝首页...")
    p, browser, context, page = _create_browser_context(headless=headless)

    try:
        page.goto("https://www.dongchedi.com", timeout=30000,
                  wait_until="networkidle")
        time.sleep(3)

        # 检测登录状态
        is_logged_in = page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if ((b.textContent || '').trim() === '登录') return false;
                }
                return true;
            }
        """)
        if is_logged_in:
            print("检测到已登录状态，跳过登录流程")
            # 仍然保存 Cookie
            cookies = context.cookies()
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _save_cookies(cookies)
            _save_session_info(phone)
            browser.close()
            p.stop()
            return COOKIE_FILE

        # 点击登录按钮
        print(f"[2/4] 触发登录弹窗...")
        login_btn = page.locator("button:has-text('登录')").first
        if login_btn.count() == 0:
            login_btn = page.locator("text=登录").first
        login_btn.click()
        time.sleep(3)

        # 验证登录弹窗出现
        phone_input = page.locator("input[name='account']")
        if phone_input.count() == 0:
            print("错误: 未找到登录表单，请确认页面加载正常")
            browser.close()
            p.stop()
            return None

        # 输入手机号
        print(f"[3/4] 填写手机号 {phone[:3]}****{phone[-4:]} ...")
        phone_input.fill(phone)
        time.sleep(0.5)

        # 点击"获取验证码"
        sms_btn = page.locator("text=获取验证码").first
        if sms_btn.count() == 0:
            print("错误: 未找到发送验证码按钮")
            browser.close()
            p.stop()
            return None

        sms_btn.click()
        print("已发送验证码，请查看手机短信")
        print()

        # 输入验证码
        max_retries = 3
        for attempt in range(max_retries):
            code = input("请输入6位短信验证码: ").strip()
            if not code or len(code) < 4:
                print("验证码格式不正确")
                continue

            code_input = page.locator("input[name='code']")
            code_input.fill(code)
            time.sleep(0.5)

            # 查找并点击登录弹窗内的提交按钮，避免点到弹窗背后的首页“登录”按钮
            submit_selectors = [
                ".login-confirm-button",
                "button.login-confirm-button",
                "button:has-text('登录/注册')",
                "button:has-text('注册/登录')",
                "button:has-text('确认')",
                "button:has-text('提交')",
            ]
            submitted = False
            for selector in submit_selectors:
                submit_btn = page.locator(selector).first
                if submit_btn.count() > 0:
                    submit_btn.click()
                    submitted = True
                    break

            if not submitted:
                # 尝试按回车提交
                page.keyboard.press("Enter")

            time.sleep(3)

            # 验证登录成功
            page.reload()
            time.sleep(2)
            logged_in = page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if ((b.textContent || '').trim() === '登录') return false;
                    }
                    // 检查是否有用户信息
                    return document.body.innerText.includes('我的') ||
                           document.body.innerText.includes('已登录');
                }
            """)

            if logged_in:
                print("\n[4/4] 登录成功！")
                break
            else:
                print(f"登录未成功，还剩 {max_retries - attempt - 1} 次尝试")
                if attempt < max_retries - 1:
                    # 重新发送验证码
                    retry_sms = input("是否重新发送验证码？(Y/n): ").strip().lower()
                    if retry_sms != 'n':
                        sms_btn = page.locator("text=获取验证码").first
                        if sms_btn.count() > 0:
                            sms_btn.click()
                            print("已重新发送验证码")
        else:
            print("登录失败：验证码重试次数已用完")
            browser.close()
            p.stop()
            return None

        # 保存 Cookie
        cookies = context.cookies()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _save_cookies(cookies)
        _save_session_info(phone)

        print(f"Cookie 已保存到: {COOKIE_FILE}")
        print(f"登录信息已保存到: {SESSION_FILE}")

        browser.close()
        p.stop()
        return COOKIE_FILE

    except Exception as e:
        print(f"登录过程出错: {e}")
        browser.close()
        p.stop()
        return None


def logout():
    """登出：清除 Cookie 和会话信息"""
    print("=" * 60)
    print("懂车帝登出工具")
    print("=" * 60)

    files_to_remove = [COOKIE_FILE, SESSION_FILE]
    removed = []
    for f in files_to_remove:
        if f.exists():
            f.unlink()
            removed.append(f.name)
            print(f"已删除: {f}")

    if not removed:
        print("没有找到登录信息（已是未登录状态）")
    else:
        print("登出完成！")


def load_cookies():
    """加载已保存的 Cookie"""
    if not COOKIE_FILE.exists():
        return None

    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        # 检查 Cookie 是否过期
        now = time.time()
        valid_cookies = [c for c in cookies if c.get("expires", -1) > now
                         or c.get("expires", -1) == -1]

        if len(valid_cookies) < len(cookies):
            print(f"注意: {len(cookies) - len(valid_cookies)} 个 Cookie 已过期")

        return valid_cookies if valid_cookies else None

    except Exception as e:
        print(f"加载 Cookie 失败: {e}")
        return None


def is_logged_in():
    """检查是否有有效的登录 Cookie"""
    cookies = load_cookies()
    if not cookies:
        return False

    # 检查是否有懂车帝相关的认证 Cookie
    auth_cookies = [c for c in cookies
                    if "dongchedi" in c.get("domain", "")
                    or "toutiao" in c.get("domain", "")
                    or "bytedance" in c.get("domain", "")]
    return len(auth_cookies) > 0


def show_status():
    """显示当前登录状态"""
    print("=" * 60)
    print("懂车帝登录状态")
    print("=" * 60)

    if not COOKIE_FILE.exists():
        print("状态: 未登录")
        print("运行 `python tools/login.py` 进行登录")
        return

    # 检查 Cookie
    cookies = load_cookies()
    if not cookies:
        print("状态: Cookie 已过期或无效")
        print("运行 `python tools/login.py` 重新登录")
        return

    print(f"状态: 已登录")
    print(f"Cookie 数量: {len(cookies)}")

    # 显示会话信息
    if SESSION_FILE.exists():
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session = json.load(f)
        print(f"手机号: {session.get('phone', 'N/A')}")
        print(f"登录时间: {session.get('login_time', 'N/A')}")

    # 检查过期时间
    max_expiry = max(
        (c.get("expires", 0) for c in cookies if c.get("expires", -1) > 0),
        default=0
    )
    if max_expiry > 0:
        remaining = max_expiry - time.time()
        if remaining > 86400:
            print(f"剩余有效期: {remaining / 86400:.1f} 天")
        elif remaining > 3600:
            print(f"剩余有效期: {remaining / 3600:.1f} 小时")
        elif remaining > 0:
            print(f"剩余有效期: {remaining / 60:.0f} 分钟")
        else:
            print("Cookie 已过期！请重新登录")
    else:
        print("Cookie 类型: 会话级（浏览器关闭后失效）")


def _save_cookies(cookies):
    """保存 Cookie 到文件"""
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def _save_session_info(phone):
    """保存会话信息"""
    info = {
        "phone": phone,
        "login_time": datetime.now().isoformat(),
        "source": "dongchedi.com",
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="懂车帝登录/登出工具")
    parser.add_argument("--phone", type=str, help="手机号")
    parser.add_argument("--logout", action="store_true", help="登出（清除 Cookie）")
    parser.add_argument("--status", action="store_true", help="查看登录状态")
    parser.add_argument("--headless", action="store_true",
                        help="无头模式（不显示浏览器）")
    args = parser.parse_args()

    if args.logout:
        logout()
    elif args.status:
        show_status()
    else:
        login(phone=args.phone, headless=args.headless)
