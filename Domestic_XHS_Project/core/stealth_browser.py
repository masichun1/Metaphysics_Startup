"""小红书 Stealth 浏览器 — 供各 Skill 调用的共享爬取层

基于 patright (Playwright undetected fork) + XHR 响应拦截。
直接从 API 返回的 JSON 提取结构化数据，不再用 HTML 正则。
"""

import asyncio
import json
import logging
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger("xhs.stealth_browser")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = PROJECT_ROOT / "data" / "browser_profiles" / "stealth"
COOKIE_PATH = PROJECT_ROOT / "data" / "cache" / "xhs_cookies.json"

# 真人操作参数 (ms)
HUMAN_DELAYS = {
    "after_page_load": (1500, 3500),
    "between_scrolls": (800, 2500),
    "after_click": (500, 2000),
    "think_pause": (1500, 4000),
}

# 小红书 API 端点 pattern → 数据类型
API_PATTERNS = {
    "/api/sns/web/v1/search/notes": "search_notes",
    "/api/sns/web/v1/search/user": "search_users",
    "/api/sns/web/v1/user_posted": "user_notes",
    "/api/sns/web/v1/board/user": "user_notes",
    "/api/sns/web/v1/user/otherinfo": "user_info",
    "/api/sns/web/v1/feed": "home_feed",
}


async def human_pause(action: str):
    """异步随机延迟"""
    lo, hi = HUMAN_DELAYS.get(action, (500, 2000))
    await asyncio.sleep(random.randint(lo, hi) / 1000)


class StealthScraper:
    """小红书数据爬取器 — XHR 拦截 + JSON 解析"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._context = None
        self._page = None
        self._cookies_loaded = False
        # XHR 响应缓存
        self._responses: list[dict] = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def start(self):
        """启动 stealth 浏览器"""
        from patchright.async_api import async_playwright

        self._playwright = await async_playwright().__aenter__()
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=self.headless,
            no_viewport=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=1440,900",
            ],
        )

        if COOKIE_PATH.exists():
            try:
                with open(COOKIE_PATH, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                await self._context.add_cookies(cookies)
                self._cookies_loaded = True
                logger.info(f"Loaded {len(cookies)} cookies")
            except Exception:
                pass

        self._page = (
            self._context.pages[0]
            if self._context.pages
            else await self._context.new_page()
        )

        # 启动 XHR 拦截
        self._setup_response_interception()

    def _setup_response_interception(self):
        """监听所有 XHR 响应，自动捕获 API 数据"""
        self._responses = []

        async def on_response(response):
            url = response.url
            for pattern, data_type in API_PATTERNS.items():
                if pattern in url:
                    try:
                        body = await response.text()
                        if len(body) < 200000:  # 小红书搜索响应通常 50-70KB
                            self._responses.append(
                                {
                                    "url": url,
                                    "type": data_type,
                                    "body": body,
                                }
                            )
                            logger.debug(f"Captured: {data_type} ({len(body)} bytes)")
                    except Exception:
                        pass
                    break

        self._page.on("response", on_response)

    async def close(self):
        """关闭浏览器"""
        try:
            if self._context:
                cookies = await self._context.cookies()
                COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
                COOKIE_PATH.write_text(
                    json.dumps(cookies, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                await self._context.close()
        except Exception:
            pass
        if self._playwright:
            await self._playwright.stop()

    async def _ensure_page(self):
        """确保有一个可用页面"""
        if not self._page or self._page.is_closed():
            self._page = (
                self._context.pages[0]
                if self._context.pages
                else await self._context.new_page()
            )
            self._setup_response_interception()
        return self._page

    def _parse_captured(self, data_type: str) -> list[dict]:
        """从缓存的 XHR 响应中解析指定类型的结构化数据"""
        notes = []
        for resp in self._responses:
            if resp["type"] != data_type:
                continue
            try:
                data = json.loads(resp["body"])
                if not data.get("success"):
                    continue
                items = data.get("data", {}).get("items", [])
                if not items:
                    items = data.get("data", {}).get("notes", [])
                if not items:
                    # user search
                    items = data.get("data", {}).get("users", [])

                for item in items:
                    note = self._normalize_item(item, data_type)
                    if note:
                        notes.append(note)
            except (json.JSONDecodeError, KeyError):
                continue

        # 去重
        seen = set()
        unique = []
        for n in notes:
            nid = n.get("note_id") or n.get("user_id") or ""
            if nid not in seen:
                seen.add(nid)
                unique.append(n)
        return unique

    def _normalize_item(self, item: dict, data_type: str) -> Optional[dict]:
        """将不同 API 返回的 item 统一为标准格式"""
        try:
            if data_type in ("search_notes", "home_feed", "user_notes"):
                # 两个 API 返回格式不同:
                # search/notes:  item.note_card.display_title, item.note_card.interact_info
                # user_posted:   item.display_title, item.interact_info (root level)
                note_card = item.get("note_card", {}) or {}
                interact = note_card.get("interact_info") or item.get("interact_info", {}) or {}
                user = note_card.get("user") or item.get("user", {}) or {}

                def _to_int(v):
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        return 0

                display_title = note_card.get("display_title") or item.get("display_title", "")
                note_id = item.get("id") or item.get("note_id", "")

                return {
                    "note_id": note_id,
                    "title": display_title,
                    "type": note_card.get("type") or item.get("type", "normal"),
                    "likes": _to_int(interact.get("liked_count", 0)),
                    "collects": _to_int(interact.get("collected_count", 0)),
                    "comments": _to_int(interact.get("comment_count", 0)),
                    "shares": _to_int(interact.get("shared_count", 0)),
                    "author": user.get("nickname") or user.get("nick_name", ""),
                    "author_id": user.get("user_id", ""),
                    "cover_type": note_card.get("type") or item.get("type", ""),
                    "tags": [
                        t.get("name", "")
                        for t in item.get("tag_list", item.get("tags", []))
                    ],
                    "time": item.get("time", 0),
                    "word_count": len(display_title),
                }
            elif data_type == "search_users":
                return {
                    "user_id": item.get("user_id", item.get("id", "")),
                    "nickname": item.get("nickname", item.get("name", "")),
                    "bio": item.get("desc", ""),
                    "fans": item.get("fans", item.get("follower_count", 0)),
                    "note_count": item.get("note_count", item.get("notes", 0)),
                    "avatar": item.get("avatar", item.get("image", "")),
                }
            elif data_type == "user_info":
                return {
                    "user_id": item.get("id", ""),
                    "nickname": item.get("nickname", ""),
                    "bio": item.get("desc", ""),
                    "fans": item.get("fans", 0),
                    "following": item.get("follows", 0),
                    "note_count": item.get("notes", 0),
                    "xhs_id": item.get("red_id", ""),
                }
        except Exception as e:
            logger.warning(f"normalize_item failed: {e}")
        return None

    def _clear_responses(self):
        """清空响应缓存（每次搜索前调用）"""
        self._responses = []

    # === 核心爬取接口 ===

    async def search_notes(self, keyword: str, count: int = 20) -> list[dict]:
        """搜索笔记 — XHR 拦截版。

        流程: 打开搜索页 → 等待 XHR 加载 → 解析 JSON → 返回结构化数据
        """
        page = await self._ensure_page()
        self._clear_responses()

        # 先访问首页建立会话上下文
        if "xiaohongshu.com" not in page.url:
            await page.goto("https://www.xiaohongshu.com", timeout=30000)
            await human_pause("after_page_load")

        # 搜索
        encoded_kw = keyword.replace(" ", "%20").replace("+", "%20")
        search_url = (
            f"https://www.xiaohongshu.com/search_result"
            f"?keyword={encoded_kw}&type=general&sort=general"
        )
        await page.goto(search_url, timeout=30000)
        await human_pause("after_page_load")

        title = await page.title()
        if "安全" in title:
            logger.warning(f"Blocked by security: {keyword}")
            return []

        # 等待 XHR 加载完成（用 asyncio.sleep 确保事件循环处理响应回调）
        for _ in range(10):
            await asyncio.sleep(1)
            notes = self._parse_captured("search_notes")
            if len(notes) >= 5:
                break

        # 模拟滚动触发更多加载
        for _ in range(min(count // 10, 3)):
            await page.mouse.wheel(0, random.randint(400, 800))
            await asyncio.sleep(random.uniform(1, 2.5))

        notes = self._parse_captured("search_notes")

        # 补全字段: 提取标签、字数
        for n in notes:
            if not n["tags"]:
                import re
                tag_match = re.findall(r"#(\S+)", n.get("title", ""))
                n["tags"] = tag_match[:8]

        logger.info(f"search_notes '{keyword}' -> {len(notes)} results")
        return notes[:count]

    async def get_user_notes(self, user_id: str, count: int = 30) -> list[dict]:
        """获取用户笔记 — XHR 拦截版"""
        page = await self._ensure_page()
        self._clear_responses()

        await page.goto(
            f"https://www.xiaohongshu.com/user/profile/{user_id}",
            timeout=30000,
        )
        await human_pause("after_page_load")

        # 滚动触发 user_notes XHR
        for _ in range(min(count // 10, 5)):
            await page.mouse.wheel(0, random.randint(400, 800))
            await human_pause("between_scrolls")

        notes = self._parse_captured("user_notes")
        logger.info(f"get_user_notes {user_id} -> {len(notes)} results")
        return notes[:count]

    async def search_users(self, keyword: str, count: int = 10) -> list[dict]:
        """搜索用户 — XHR 拦截版"""
        page = await self._ensure_page()
        self._clear_responses()

        if "xiaohongshu.com" not in page.url:
            await page.goto("https://www.xiaohongshu.com", timeout=30000)
            await human_pause("after_page_load")

        encoded = keyword.replace(" ", "%20")
        await page.goto(
            f"https://www.xiaohongshu.com/search_result?keyword={encoded}&type=user",
            timeout=30000,
        )
        await human_pause("after_page_load")

        # 等待 XHR
        for _ in range(5):
            await page.wait_for_timeout(1000)
            users = self._parse_captured("search_users")
            if users:
                break

        # 也尝试从 search_notes 的 author 字段提取
        if not users:
            note_results = self._parse_captured("search_notes")
            seen = set()
            for n in note_results:
                aid = n.get("author_id")
                aname = n.get("author")
                if aid and aid not in seen:
                    seen.add(aid)
                    users.append(
                        {
                            "user_id": aid,
                            "nickname": aname,
                            "bio": "",
                            "fans": 0,
                            "note_count": 0,
                        }
                    )

        logger.info(f"search_users '{keyword}' -> {len(users)} results")
        return users[:count]

    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """获取用户基本信息"""
        page = await self._ensure_page()
        self._clear_responses()

        await page.goto(
            f"https://www.xiaohongshu.com/user/profile/{user_id}",
            timeout=30000,
        )
        await human_pause("after_page_load")
        await page.wait_for_timeout(3000)

        users = self._parse_captured("user_info")
        if users:
            return users[0]
        return None

    async def get_home_feed(self, scrolls: int = 5) -> list[dict]:
        """获取首页推荐流"""
        page = await self._ensure_page()
        self._clear_responses()

        await page.goto("https://www.xiaohongshu.com/explore", timeout=30000)
        await human_pause("after_page_load")

        for _ in range(scrolls):
            await page.mouse.wheel(0, random.randint(300, 700))
            await human_pause("between_scrolls")

        notes = self._parse_captured("home_feed")
        logger.info(f"get_home_feed -> {len(notes)} results")
        return notes


@asynccontextmanager
async def stealth_scraper(headless: bool = True):
    """上下文管理器 — 自动管理浏览器生命周期"""
    scraper = StealthScraper(headless=headless)
    try:
        await scraper.start()
        yield scraper
    finally:
        await scraper.close()
