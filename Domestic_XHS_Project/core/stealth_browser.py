"""小红书 Stealth 浏览器 — 供各 Skill 调用的共享爬取层

基于 patright (Playwright undetected fork) + humanization 行为拟人化。
所有对外请求走真实浏览器，不再用 AI 凭空生成数据。
"""

import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger("xhs.stealth_browser")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = PROJECT_ROOT / "data" / "browser_profiles" / "stealth"
COOKIE_PATH = PROJECT_ROOT / "data" / "cache" / "xhs_cookies.json"
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"

# 真人操作参数
HUMAN_DELAYS = {
    "after_page_load": (2000, 4000),
    "between_scrolls": (800, 3000),
    "before_click": (200, 800),
    "after_click": (500, 2000),
    "typing_char": (60, 180),  # ms per character
    "think_pause": (1500, 5000),
}


def human_delay(action: str) -> None:
    """同步版随机延迟（用于同步代码）"""
    lo, hi = HUMAN_DELAYS.get(action, (500, 2000))
    time.sleep(random.randint(lo, hi) / 1000)


async def human_pause(action: str):
    """异步随机延迟"""
    lo, hi = HUMAN_DELAYS.get(action, (500, 2000))
    await asyncio.sleep(random.randint(lo, hi) / 1000)


class StealthScraper:
    """小红书数据爬取器 — 所有 Skill 的底层浏览器"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._cookies_loaded = False

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

        # 加载已有 cookie
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

    async def close(self):
        """关闭浏览器"""
        if self._page:
            await self._page.close()
        if self._context:
            # 保存 cookie
            try:
                cookies = await self._context.cookies()
                COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
                COOKIE_PATH.write_text(
                    json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                logger.info(f"Saved {len(cookies)} cookies")
            except Exception:
                pass
            await self._context.close()
        if self._playwright:
            await self._playwright.__aexit__(None, None, None)

    async def _ensure_page(self):
        """确保有一个可用页面"""
        if not self._page or self._page.is_closed():
            self._page = (
                self._context.pages[0]
                if self._context.pages
                else await self._context.new_page()
            )
        return self._page

    def _parse_api_response(self, text: str) -> Optional[dict]:
        """解析 API 响应 JSON"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # === 核心爬取操作 ===

    async def search_notes(
        self, keyword: str, count: int = 20
    ) -> list[dict]:
        """搜索笔记并返回结构化数据。

        Args:
            keyword: 搜索关键词
            count: 最多返回条数

        Returns:
            [{"title": "", "likes": 0, "collects": 0, "comments": 0,
              "author": "", "note_id": "", "cover_type": "", "hashtags": []}, ...]
        """
        page = await self._ensure_page()
        results = []

        # 先确保在首页
        await page.goto("https://www.xiaohongshu.com", timeout=30000)
        await human_pause("after_page_load")

        # 搜索
        encoded_kw = keyword.replace(" ", "%20")
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_kw}&type=general&sort=general"
        await page.goto(search_url, timeout=30000)
        await human_pause("after_page_load")

        # 检查是否被安全拦截
        title = await page.title()
        if "安全" in title:
            logger.warning(f"Search blocked by security for keyword: {keyword}")
            return results

        # 模拟人类滚动加载更多
        for _ in range(min(count // 10, 5)):
            await page.mouse.wheel(0, random.randint(400, 800))
            await human_pause("between_scrolls")

        # 从页面 HTML 中提取笔记数据
        html = await page.content()

        # 小红书搜索结果在 SSR HTML 中以 note_id 和 display_title 字段嵌入
        import re

        # 提取 note_id
        note_ids = re.findall(r'"note_id"\s*:\s*"([a-f0-9]{24,32})"', html)
        # 提取标题
        titles = re.findall(r'"display_title"\s*:\s*"([^"]*)"', html)
        # 提取互动数据
        liked_counts = re.findall(r'"liked_count"\s*:\s*(\d+)', html)
        collected_counts = re.findall(r'"collected_count"\s*:\s*(\d+)', html)
        comment_counts = re.findall(r'"comment_count"\s*:\s*(\d+)', html)

        for i, note_id in enumerate(note_ids[:count]):
            note = {
                "note_id": note_id,
                "title": titles[i] if i < len(titles) else "",
                "likes": int(liked_counts[i]) if i < len(liked_counts) else 0,
                "collects": int(collected_counts[i]) if i < len(collected_counts) else 0,
                "comments": int(comment_counts[i]) if i < len(comment_counts) else 0,
            }
            results.append(note)

        logger.info(f"search_notes keyword={keyword} found={len(results)}")
        return results

    async def get_user_notes(
        self, user_id: str, count: int = 30
    ) -> list[dict]:
        """获取指定用户的所有公开笔记。

        Args:
            user_id: 用户 ID（24-32位 hex）
            count: 最多获取条数

        Returns:
            [{"title": "", "note_id": "", "type": "", "likes": 0, ...}, ...]
        """
        page = await self._ensure_page()

        # 直接访问用户主页
        await page.goto(
            f"https://www.xiaohongshu.com/user/profile/{user_id}",
            timeout=30000,
        )
        await human_pause("after_page_load")

        title = await page.title()
        if "安全" in title or "小红书" not in title:
            logger.warning(f"Profile blocked for user_id: {user_id}")
            return []

        # 等待页面加载
        await page.wait_for_timeout(2000)

        # 滚动加载
        for _ in range(min(count // 10, 5)):
            await page.mouse.wheel(0, random.randint(400, 800))
            await human_pause("between_scrolls")

        html = await page.content()
        import re

        notes = []
        note_ids = re.findall(r'"note_id"\s*:\s*"([a-f0-9]{24,32})"', html)
        titles = re.findall(r'"display_title"\s*:\s*"([^"]*)"', html)
        note_types = re.findall(r'"type"\s*:\s*"(\w+)"', html)
        liked_counts = re.findall(r'"liked_count"\s*:\s*(\d+)', html)
        collected_counts = re.findall(r'"collected_count"\s*:\s*(\d+)', html)
        comment_counts = re.findall(r'"comment_count"\s*:\s*(\d+)', html)
        timestamps = re.findall(r'"time"\s*:\s*(\d+)', html)

        for i, note_id in enumerate(note_ids[:count]):
            notes.append(
                {
                    "note_id": note_id,
                    "title": titles[i] if i < len(titles) else "",
                    "type": note_types[i] if i < len(note_types) else "normal",
                    "likes": int(liked_counts[i]) if i < len(liked_counts) else 0,
                    "collects": int(collected_counts[i]) if i < len(collected_counts) else 0,
                    "comments": int(comment_counts[i]) if i < len(comment_counts) else 0,
                    "time": int(timestamps[i]) if i < len(timestamps) else 0,
                }
            )

        logger.info(f"get_user_notes user_id={user_id} found={len(notes)}")
        return notes

    async def search_users(
        self, keyword: str, count: int = 10
    ) -> list[dict]:
        """搜索用户。

        Returns:
            [{"nickname": "", "user_id": "", "fans": 0, "notes": 0, "bio": ""}, ...]
        """
        page = await self._ensure_page()

        encoded = keyword.replace(" ", "%20")
        await page.goto(
            f"https://www.xiaohongshu.com/search_result?keyword={encoded}&type=user",
            timeout=30000,
        )
        await human_pause("after_page_load")

        title = await page.title()
        if "安全" in title:
            logger.warning(f"User search blocked: {keyword}")
            return []

        html = await page.content()
        import re

        users = []
        user_ids = re.findall(r'"user_id"\s*:\s*"([a-f0-9]{24,32})"', html)
        nicknames = re.findall(r'"nickname"\s*:\s*"([^"]*)"', html)
        fans = re.findall(r'"fans"\s*:\s*(\d+)', html)
        note_counts = re.findall(r'"note_count"\s*:\s*(\d+)', html)
        bios = re.findall(r'"desc"\s*:\s*"([^"]*)"', html)

        for i, uid in enumerate(user_ids[:count]):
            users.append(
                {
                    "user_id": uid,
                    "nickname": nicknames[i] if i < len(nicknames) else "",
                    "fans": int(fans[i]) if i < len(fans) else 0,
                    "note_count": int(note_counts[i]) if i < len(note_counts) else 0,
                    "bio": bios[i] if i < len(bios) else "",
                }
            )

        logger.info(f"search_users keyword={keyword} found={len(users)}")
        return users

    async def get_home_feed(self, scrolls: int = 5) -> list[dict]:
        """获取首页推荐流笔记（需要登录态）。

        Returns:
            推荐笔记列表
        """
        page = await self._ensure_page()

        await page.goto("https://www.xiaohongshu.com/explore", timeout=30000)
        await human_pause("after_page_load")

        for _ in range(scrolls):
            await page.mouse.wheel(0, random.randint(300, 700))
            await human_pause("between_scrolls")

        html = await page.content()
        import re

        notes = []
        note_ids = re.findall(r'"note_id"\s*:\s*"([a-f0-9]{24,32})"', html)
        titles = re.findall(r'"display_title"\s*:\s*"([^"]*)"', html)
        liked_counts = re.findall(r'"liked_count"\s*:\s*(\d+)', html)
        author_names = re.findall(r'"nickname"\s*:\s*"([^"]*)"', html)

        for i, note_id in enumerate(note_ids):
            notes.append(
                {
                    "note_id": note_id,
                    "title": titles[i] if i < len(titles) else "",
                    "likes": int(liked_counts[i]) if i < len(liked_counts) else 0,
                    "author": author_names[i] if i < len(author_names) else "",
                }
            )

        logger.info(f"get_home_feed found={len(notes)}")
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
