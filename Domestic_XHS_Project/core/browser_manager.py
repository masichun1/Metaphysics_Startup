"""OpenCLI browser manager — Playwright wrapper with anti-detection measures.

This is the "四肢/眼睛" layer that executes browser operations.
Claude (大脑) generates the strategy, BrowserManager executes it.
"""

import json
import logging
import random
import time
from pathlib import Path
from typing import Any

from core.config_loader import BrowserConfig
from core.exceptions import (
    BrowserError,
    CaptchaError,
    CookieExpiredError,
    LoginError,
    RateLimitError,
)

logger = logging.getLogger("xhs.browser")

# Attempt to import Playwright — it's optional at import time
try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class BrowserManager:
    """Manages a Playwright browser instance with anti-detection for XHS.

    Key anti-detection measures:
    - Stealth mode (playwright-stealth)
    - Randomized action delays
    - Human-like mouse movement
    - Cookie/session persistence
    - Proxy support
    - Rate limit detection and cooldown
    """

    def __init__(self, config: BrowserConfig, cookie_path: str = "data/cache/cookies.json"):
        if not HAS_PLAYWRIGHT:
            raise ImportError(
                "playwright is required. Run: pip install playwright && playwright install chromium"
            )
        self.config = config
        self.cookie_path = Path(cookie_path)
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._request_count = 0
        self._session_start = time.monotonic()
        self._cooldown_until = 0.0

    def start(self) -> "BrowserManager":
        """Launch browser and load saved session."""
        self._playwright = sync_playwright().start()

        launch_options: dict[str, Any] = {
            "headless": self.config.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        if self.config.proxy_url:
            launch_options["proxy"] = {"server": self.config.proxy_url}

        self._browser = self._playwright.chromium.launch(**launch_options)

        # Load cookies if available
        storage_state = None
        if self.cookie_path.exists():
            try:
                storage_state = str(self.cookie_path)
            except Exception:
                pass

        self._context = self._browser.new_context(
            user_agent=self.config.user_agent,
            storage_state=storage_state,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        self._page = self._context.new_page()
        logger.info("browser_started", headless=self.config.headless)
        return self

    def stop(self) -> None:
        """Save cookies and close browser."""
        if self._context and self._page:
            # Save cookies for reuse
            try:
                cookies = self._context.cookies()
                self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
                self.cookie_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
                logger.info("cookies_saved", path=str(self.cookie_path))
            except Exception as e:
                logger.error("cookie_save_failed", error=str(e))

        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("browser_stopped")

    @property
    def page(self) -> Page:
        if not self._page:
            raise BrowserError("Browser not started. Call start() first.")
        return self._page

    def human_delay(self, min_ms: int | None = None, max_ms: int | None = None) -> None:
        """Random delay to simulate human behavior."""
        min_delay = min_ms if min_ms is not None else self.config.action_delay_min_ms
        max_delay = max_ms if max_ms is not None else self.config.action_delay_max_ms
        delay_ms = random.randint(min_delay, max_delay) / 1000.0
        time.sleep(delay_ms)

    def human_scroll(self, distance: int = 300) -> None:
        """Simulate human-like scrolling."""
        for _ in range(random.randint(1, 3)):
            self._page.mouse.wheel(0, distance * random.uniform(0.5, 1.5))
            self.human_delay(200, 800)

    def safe_goto(self, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL with rate limit awareness."""
        self._check_cooldown()

        for attempt in range(1, max_retries + 1):
            try:
                self._page.goto(url, timeout=self.config.page_timeout_ms, wait_until="domcontentloaded")
                self._request_count += 1
                self.human_delay()
                self._detect_captcha()
                return True
            except Exception as e:
                logger.warning("goto_failed", url=url, attempt=attempt, error=str(e))
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
        raise BrowserError(f"Failed to navigate to {url} after {max_retries} attempts")

    def check_rate_limit(self) -> bool:
        """Check if we're being rate-limited. Returns True if safe to proceed."""
        # Monitor request frequency — max ~30 requests/minute
        elapsed = time.monotonic() - self._session_start
        rpm = (self._request_count / elapsed) * 60 if elapsed > 0 else 0
        if rpm > 30:
            cooldown = random.uniform(60, 180)
            logger.warning("rate_limit_cooldown", rpm=int(rpm), cooldown_s=int(cooldown))
            self._cooldown_until = time.monotonic() + cooldown
            return False
        return True

    def _check_cooldown(self) -> None:
        """Block if in cooldown period."""
        if time.monotonic() < self._cooldown_until:
            remaining = self._cooldown_until - time.monotonic()
            logger.info("cooldown_wait", remaining_s=int(remaining))
            time.sleep(remaining)

    def _detect_captcha(self) -> None:
        """Check page for CAPTCHA triggers."""
        page_text = self._page.content().lower()
        captcha_signals = [
            "请通过验证", "验证码", "captcha", "slide to verify",
            "请完成验证", "系统检测到异常",
        ]
        for signal in captcha_signals:
            if signal in page_text:
                raise CaptchaError(f"CAPTCHA detected on page: {self._page.url}")

    def type_like_human(self, selector: str, text: str) -> None:
        """Type text with human-like delays between keystrokes."""
        element = self._page.wait_for_selector(selector, timeout=10000)
        element.click()
        self.human_delay()
        for char in text:
            element.type(char, delay=random.randint(50, 250))
        self.human_delay()
