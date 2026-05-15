import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from core.exceptions import ConfigError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class BrowserConfig(BaseModel):
    headless: bool = True
    proxy_url: str | None = None
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    page_timeout_ms: int = 30000
    action_delay_min_ms: int = 500
    action_delay_max_ms: int = 5000


class XHSAccountConfig(BaseModel):
    username: str = ""
    password: str = ""
    cookie_path: str = "data/cache/cookies.json"


class AppConfig(BaseModel):
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    xhs_account: XHSAccountConfig = Field(default_factory=XHSAccountConfig)
    log_level: str = "INFO"
    data_db_path: str = "data/cache/xhs_data.db"


def load_config(env_path: str | Path | None = None) -> AppConfig:
    """Load config from .env file."""
    env_path = Path(env_path) if env_path else _PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)

    return AppConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv(
            "ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-20250514"
        ),
        browser=BrowserConfig(
            headless=os.getenv("OPENCLI_BROWSER_HEADLESS", "false").lower() == "true",
            proxy_url=os.getenv("OPENCLI_PROXY_URL"),
            user_agent=os.getenv("OPENCLI_USER_AGENT", BrowserConfig.model_fields["user_agent"].default),
            page_timeout_ms=int(os.getenv("OPENCLI_PAGE_TIMEOUT_MS", "30000")),
            action_delay_min_ms=int(os.getenv("OPENCLI_ACTION_DELAY_MIN_MS", "500")),
            action_delay_max_ms=int(os.getenv("OPENCLI_ACTION_DELAY_MAX_MS", "5000")),
        ),
        xhs_account=XHSAccountConfig(
            username=os.getenv("XHS_USERNAME", ""),
            password=os.getenv("XHS_PASSWORD", ""),
            cookie_path=os.getenv("XHS_COOKIE_PATH", "data/cache/cookies.json"),
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        data_db_path=os.getenv("DATA_DB_PATH", "data/cache/xhs_data.db"),
    )
