#!/usr/bin/env python3
"""小红书反检测浏览器模块 — 解决"第三方脚本/AI自动化检测"问题

基于GitHub开源方案整合：
- Patchright (Playwright undetected fork): github.com/Kaliiiiiiiiii-Vinyzu/patchright
- rebrowser-patches: github.com/rebrowser/rebrowser-patches
- XHS_RS_TOOLS 策略: github.com/aki66938/XHS_RS_TOOLS
- redbookc 反检测策略: github.com/brettinhere/redbookc

核心原理：
1. CDP 泄漏修复 — 消除 Runtime.enable / Console.enable 等检测信号
2. 真实 Chrome + 独立 Profile — 每个账号独立的浏览器环境(含历史/书签/Cookie)
3. 行为拟人化 — 贝塞尔鼠标轨迹、变速打字、随机思考停顿
4. 多账号隔离 — 一机一号一IP，账号间完全隔离
"""

import logging
import random
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("xhs.antidetect")

# Chrome Profile 根目录
_PROFILE_ROOT = Path(__file__).resolve().parent.parent / "data" / "browser_profiles"

# 反检测 JS 注入脚本 (在页面加载前注入)
PRELOAD_STEALTH_SCRIPT = """
// === 小红书反检测脚本 v2 ===
// 覆盖 navigator 属性
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

// 覆盖 chrome 对象
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// 覆盖权限查询
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// 覆盖 headless 检测
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// 消除 CDP 运行时特征
if (window.TrustedTypes) {
    // 保持 TrustedTypes 不变，避免触发异常检测
}
"""


class StealthBrowser:
    """小红书专用反检测浏览器"""

    def __init__(
        self,
        account_name: str,
        headless: bool = False,
        proxy_url: Optional[str] = None,
    ):
        self.account_name = account_name
        self.headless = headless
        self.proxy_url = proxy_url
        self.profile_dir = _PROFILE_ROOT / account_name
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self._browser = None
        self._context = None
        self._page = None

    async def launch(self) -> None:
        """启动反检测浏览器实例。

        关键配置：
        - channel="chrome": 使用真实Chrome而非Chromium
        - launch_persistent_context: 持久化Profile，积累浏览历史
        - headless=False: 非无头模式，避免秒级检测
        - no_viewport=True: 使用真实屏幕分辨率
        """
        try:
            from patchright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "请先安装 patchright: pip install patchright && patchright install chrome\n"
                "Patchright 是 Playwright 的反检测分支，修复了 CDP 泄漏问题。"
            )

        self._pw = await async_playwright().__aenter__()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            f"--user-data-dir={self.profile_dir}",
        ]

        if self.proxy_url:
            launch_args.append(f"--proxy-server={self.proxy_url}")

        self._context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="chrome",
            headless=self.headless,
            no_viewport=True,
            args=launch_args,
            # 不设置 viewport，使用真实屏幕分辨率
            # 不设置 user_agent，让 Patchright 处理
        )

        # 注入反检测脚本到所有页面
        await self._context.add_init_script(PRELOAD_STEALTH_SCRIPT)

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        logger.info(f"stealth_browser_launched account={self.account_name} profile={self.profile_dir}")

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._pw:
            await self._pw.__aexit__(None, None, None)

    async def human_type(self, selector: str, text: str, wpm: int = 60) -> None:
        """模拟人类打字节奏。

        Args:
            selector: 目标输入框选择器
            text: 要输入的文字
            wpm: 打字速度(字/分钟)，默认60(中文正常速度)
        """
        el = await self._page.wait_for_selector(selector)
        await el.click()

        chars_per_second = wpm / 60
        for i, char in enumerate(text):
            await self._page.keyboard.type(char, delay=0)
            # 模拟思考停顿：长词后、标点后概率性停顿
            if char in "，。！？；：、" and random.random() < 0.3:
                await self._page.wait_for_timeout(random.randint(300, 1200))
            elif (i + 1) % 5 == 0 and random.random() < 0.1:
                await self._page.wait_for_timeout(random.randint(150, 600))
            else:
                base_delay = 60 / chars_per_second
                jitter = random.gauss(0, base_delay * 0.3)
                await self._page.wait_for_timeout(max(30, int(base_delay + jitter)))

    async def human_scroll(self, distance: int = None, duration_ms: int = None) -> None:
        """模拟人类滚动行为。

        真人滚动特征：
        - 不均匀速度（先快后慢或先慢后快）
        - 微小横向漂移
        - 概率性回滚(往回看一眼)
        """
        if distance is None:
            distance = random.randint(300, 800)
        if duration_ms is None:
            duration_ms = random.randint(800, 2500)

        steps = random.randint(8, 20)
        step_delay = duration_ms / steps

        for i in range(steps):
            progress = i / steps
            # 缓入缓出曲线
            eased = progress ** 2 * (3 - 2 * progress)
            current_y = int(distance * eased)
            drift_x = random.randint(-3, 3)

            await self._page.mouse.wheel(drift_x, current_y // steps)
            await self._page.wait_for_timeout(int(step_delay))

        # 10% 概率回滚
        if random.random() < 0.1:
            rollback = random.randint(50, 200)
            await self._page.mouse.wheel(0, -rollback)
            await self._page.wait_for_timeout(random.randint(500, 1500))

    async def human_click(self, selector: str) -> None:
        """模拟人类点击：鼠标移动到元素 + 微小偏移 + 点击"""
        el = await self._page.wait_for_selector(selector)
        box = await el.bounding_box()
        if box:
            # 点击元素内部的随机位置，而非正中心
            target_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
            target_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
            await self._page.mouse.move(target_x, target_y)
            await self._page.wait_for_timeout(random.randint(50, 200))
            await self._page.mouse.click(target_x, target_y)
        else:
            await el.click()

    async def random_pause(self, min_ms: int = 500, max_ms: int = 5000) -> None:
        """随机停顿，模拟阅读/思考时间"""
        await self._page.wait_for_timeout(random.randint(min_ms, max_ms))


class MultiAccountManager:
    """多账号隔离管理器

    每个账号独立的：
    - Chrome Profile（含独立的历史/书签/Cookie/存储）
    - 浏览器窗口
    - IP代理（可选）
    """

    def __init__(self):
        self._browsers: dict[str, StealthBrowser] = {}

    async def get_account(self, account_name: str, proxy_url: str = None) -> StealthBrowser:
        if account_name not in self._browsers:
            browser = StealthBrowser(
                account_name=account_name,
                headless=False,
                proxy_url=proxy_url,
            )
            await browser.launch()
            self._browsers[account_name] = browser
        return self._browsers[account_name]

    async def close_all(self):
        for name, browser in self._browsers.items():
            await browser.close()
        self._browsers.clear()


# === 快速集成函数 ===

async def create_stealth_page(account: str) -> StealthBrowser:
    """为指定账号创建一个反检测浏览器页面"""
    browser = StealthBrowser(account_name=account, headless=False)
    await browser.launch()
    return browser


# === 风控规避协议 ===
# 所有操作必须遵循以下规则：

SAFETY_RULES = {
    "min_action_interval_ms": 500,      # 最小操作间隔
    "max_action_interval_ms": 5000,     # 最大操作间隔
    "max_actions_per_hour": 200,         # 每小时最大操作数
    "max_posts_per_day": 3,              # 每天最大发帖数
    "max_comments_per_hour": 10,         # 每小时最大评论数
    "max_likes_per_hour": 50,            # 每小时最大点赞数
    "active_hours": (8, 22),             # 活跃时间段(早8-晚10)
    "browse_before_action_min": 3,       # 每次操作前至少浏览3分钟
    "no_action_pattern": True,           # 禁止固定模式(间隔要随机)
    "fingerprint_consistency": True,     # 指纹一致性检查
}
