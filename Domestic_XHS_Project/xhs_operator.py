#!/usr/bin/env python3
"""小红书运营操作器 — Playwright 直接控制浏览器

基于已安装的 Playwright，无需额外 Chrome 扩展。
Claude 是大脑，Playwright 是四肢。
"""

import json
import random
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

COOKIE_PATH = Path(__file__).parent / "data" / "cache" / "xhs_cookies.json"
DATA_DIR = Path(__file__).parent / "data" / "exports"


class XHSOperator:
    """小红书浏览器操作器

    功能:
    - 登录/保持登录态 (Cookie 持久化)
    - 搜索笔记
    - 查看笔记详情 + 评论
    - 发布笔记
    - 查看创作者数据
    - 评论互动
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        """启动浏览器并加载保存的 Cookie"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ],
        )

        # Load saved cookies if available
        storage_state = None
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if COOKIE_PATH.exists():
            try:
                storage_state = str(COOKIE_PATH)
                print(f"[OK] Loaded saved session from {COOKIE_PATH}")
            except Exception:
                pass

        self.context = self.browser.new_context(
            storage_state=storage_state,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # Apply stealth patches
        if HAS_STEALTH:
            self.context = stealth_sync(self.context)

        self.page = self.context.new_page()

        # Inject additional anti-detection
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)
        return self

    def stop(self):
        """保存 Cookie 并关闭浏览器"""
        if self.context:
            cookies = self.context.cookies()
            COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
            COOKIE_PATH.write_text(json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[OK] Session saved")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()

    # ============================================================
    # 核心操作
    # ============================================================

    def login_with_qr(self):
        """打开小红书登录页，等待用户扫码登录"""
        print("[*] Opening XHS login page...")
        self.page.goto("https://www.xiaohongshu.com/explore", timeout=30000,
                       wait_until="domcontentloaded")
        self._random_delay(2, 3)

        # 检查是否已登录
        if self._is_logged_in():
            print("[OK] Already logged in!")
            return True

        print("[*] Please scan QR code to log in (phone: 17514046772)...")
        print("[*] Waiting for login (max 120 seconds)...")

        # 等待登录成功（检查 Cookie 或页面元素）
        for i in range(120):
            time.sleep(1)
            if self._is_logged_in():
                print(f"[OK] Login successful after {i+1}s!")
                self._save_session()
                return True
            if i % 10 == 0:
                print(f"    Waiting... {i}s")

        print("[FAIL] Login timed out")
        return False

    def search_notes(self, keyword: str, count: int = 20) -> list[dict]:
        """搜索小红书笔记"""
        print(f"[*] Searching: {keyword}")
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
        self.page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
        self._random_delay(2, 4)

        # 滚动加载更多
        for _ in range(3):
            self.page.keyboard.press("End")
            self._random_delay(1, 2)

        # 提取笔记信息
        notes = self.page.evaluate("""
            () => {
                const cards = document.querySelectorAll('section.note-item, .note-item, [class*="note"]');
                const results = [];
                cards.forEach((card, i) => {
                    const title = card.querySelector('.title, .note-title, [class*="title"]')?.textContent?.trim() || '';
                    const author = card.querySelector('.author .name, .nickname, [class*="author"]')?.textContent?.trim() || '';
                    const likes = card.querySelector('.like-count, .count, [class*="like"]')?.textContent?.trim() || '0';
                    const link = card.querySelector('a')?.href || '';
                    if (title) results.push({ title, author, likes, link });
                });
                                return results.slice(0, 50);
            }
        """)

        print(f"[OK] Found {len(notes)} notes for '{keyword}'")
        return notes[:count]

    def get_note_detail(self, note_url: str) -> dict:
        """获取笔记详情和评论"""
        print(f"[*] Fetching note: {note_url[:60]}...")
        self.page.goto(note_url, timeout=30000, wait_until="domcontentloaded")
        self._random_delay(2, 3)

        # 获取内容
        content = self.page.evaluate("""
            () => {
                const title = document.querySelector('#detail-title, .title')?.textContent?.trim() || '';
                const body = document.querySelector('#detail-desc, .note-text, .desc')?.textContent?.trim() || '';
                const likes = document.querySelector('.like-wrapper .count, [class*="like"] span')?.textContent?.trim() || '0';
                const collects = document.querySelector('.collect-wrapper .count, [class*="collect"] span')?.textContent?.trim() || '0';
                const comments = document.querySelector('.chat-wrapper .count, [class*="comment"] span')?.textContent?.trim() || '0';
                return { title, body, likes, collects, comments };
            }
        """)

        # 获取标签
        tags = self.page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('.tag, .topic, [class*="tag"] a')).map(t => t.textContent.trim()).filter(Boolean);
            }
        """)

        content["tags"] = tags
        content["url"] = note_url
        print(f"[OK] {content['title'][:40]} | ❤️{content['likes']} ⭐{content['collects']} 💬{content['comments']}")
        return content

    def get_comments(self, note_url: str, max_comments: int = 50) -> list[dict]:
        """获取笔记评论"""
        self.page.goto(note_url, timeout=30000, wait_until="domcontentloaded")
        self._random_delay(2, 3)

        # 滚动到评论区
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
        self._random_delay(1, 2)

        comments = self.page.evaluate("""
            (maxCount) => {
                const items = document.querySelectorAll('.comment-item, [class*="comment"]');
                const results = [];
                items.forEach(item => {
                    const user = item.querySelector('.name, .nickname, [class*="user"]')?.textContent?.trim() || '';
                    const text = item.querySelector('.content, .comment-text, [class*="content"]')?.textContent?.trim() || '';
                    const time = item.querySelector('.date, .time, [class*="date"]')?.textContent?.trim() || '';
                    if (text) results.push({ user, text, time });
                });
                return results.slice(0, maxCount);
            }
        """, max_comments)

        print(f"[OK] Got {len(comments)} comments")
        return comments

    def publish_note(self, title: str, content: str, images: list[str] | None = None, tags: list[str] | None = None):
        """发布小红书笔记 (通过创作者中心)"""
        print(f"[*] Publishing note: {title[:30]}...")
        # 导航到创作者中心
        self.page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=30000,
                       wait_until="domcontentloaded")
        self._random_delay(2, 4)

        # 上传图片
        if images:
            file_input = self.page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(images)
                self._random_delay(2, 4)
                print(f"[OK] Uploaded {len(images)} images")

        # 填写标题
        title_input = self.page.query_selector('[placeholder*="标题"], .title-input input, #title')
        if title_input:
            title_input.click()
            self._random_delay(0.5, 1)
            for char in title:
                title_input.type(char, delay=random.randint(50, 150))
            self._random_delay(1, 2)

        # 填写正文
        content_input = self.page.query_selector('[placeholder*="正文"], .content-input, #content, [contenteditable="true"]')
        if content_input:
            content_input.click()
            self._random_delay(0.5, 1)
            for char in content:
                content_input.type(char, delay=random.randint(30, 100))
            self._random_delay(1, 2)

        # 添加标签
        if tags:
            for tag in tags:
                self.page.keyboard.type(f" #{tag}")
                self._random_delay(0.3, 0.8)

        print(f"[OK] Note prepared: {title[:30]}...")
        print("[*] Manual review required before publishing. Please check the browser.")

    # ============================================================
    # 辅助方法
    # ============================================================

    def _is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            cookies = self.context.cookies("https://www.xiaohongshu.com")
            has_session = any("web_session" in c.get("name", "") or "a1" in c.get("name", "") for c in cookies)
            if has_session:
                return True

            # 也检查页面元素
            logged_in = self.page.evaluate("""
                () => {
                    return !!document.cookie.includes('web_session') ||
                           !!document.querySelector('.user-info, .avatar, [class*="login"]');
                }
            """)
            return logged_in
        except Exception:
            return False

    def _save_session(self):
        """保存当前会话"""
        cookies = self.context.cookies()
        COOKIE_PATH.write_text(json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _random_delay(min_s: float = 0.5, max_s: float = 3.0):
        time.sleep(random.uniform(min_s, max_s))


# ============================================================
# CLI 入口
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="小红书自动化运营工具")
    sub = parser.add_subparsers(dest="cmd")

    # login
    sub.add_parser("login", help="登录小红书")

    # search
    search_p = sub.add_parser("search", help="搜索笔记")
    search_p.add_argument("keyword", help="搜索关键词")
    search_p.add_argument("-n", "--count", type=int, default=20)

    # note
    note_p = sub.add_parser("note", help="查看笔记详情")
    note_p.add_argument("url", help="笔记 URL")

    # comments
    comments_p = sub.add_parser("comments", help="查看评论")
    comments_p.add_argument("url", help="笔记 URL")

    # publish
    publish_p = sub.add_parser("publish", help="发布笔记")
    publish_p.add_argument("title", help="笔记标题")
    publish_p.add_argument("content", help="笔记正文")
    publish_p.add_argument("--images", nargs="+", help="图片路径")
    publish_p.add_argument("--tags", nargs="+", help="标签")

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    with XHSOperator(headless=False) as op:
        if args.cmd == "login":
            op.login_with_qr()
            input("Press Enter after reviewing...")

        elif args.cmd == "search":
            op.login_with_qr()
            notes = op.search_notes(args.keyword, args.count)
            for n in notes:
                print(f"  {n['title'][:50]} | {n['author']} | ❤️{n['likes']}")

        elif args.cmd == "note":
            op.login_with_qr()
            detail = op.get_note_detail(args.url)
            print(json.dumps(detail, indent=2, ensure_ascii=False))

        elif args.cmd == "comments":
            op.login_with_qr()
            comments = op.get_comments(args.url)
            for c in comments:
                print(f"  [{c['time']}] {c['user']}: {c['text'][:80]}")

        elif args.cmd == "publish":
            op.login_with_qr()
            op.publish_note(args.title, args.content, args.images, args.tags)
            input("Review the note in browser, then press Enter to close...")
