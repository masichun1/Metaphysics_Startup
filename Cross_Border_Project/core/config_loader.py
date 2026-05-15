import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from core.exceptions import InvalidConfigError, MissingApiKeyError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"


# --- Pydantic config models ---

class WooCommerceConfig(BaseModel):
    site_url: str
    consumer_key: str
    consumer_secret: str
    primary_currency: str = "USD"
    weight_unit: str = "lb"


class WordPressConfig(BaseModel):
    site_url: str = ""
    username: str = ""
    app_password: str = ""


class ShopifyConfig(BaseModel):
    domain: str = ""
    api_version: str = "2024-01"
    access_token: str = ""
    location_id: int | None = None
    primary_currency: str = "USD"
    weight_unit: str = "lb"


class StoreInfoConfig(BaseModel):
    store_name: str = "Mystic Sanctuary"
    contact_email: str = "support@example.com"
    whatsapp: str = ""
    social_links: dict[str, str] = Field(default_factory=dict)


class AIDefaults(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 1024


class ContentRulesConfig(BaseModel):
    brand_voice: dict[str, Any] = Field(default_factory=dict)
    ai_defaults: dict[str, AIDefaults] = Field(default_factory=dict)


class SkillItemConfig(BaseModel):
    enabled: bool = False


class Skill01Config(SkillItemConfig):
    batch_size: int = 5
    upsert_mode: bool = True
    schedule: str = "0 * * * *"


class Skill02Config(SkillItemConfig):
    reviews_per_product_min: int = 3
    reviews_per_product_max: int = 7
    daily_max_reviews: int = 10
    rating_distribution_target: dict[int, float] = Field(default_factory=dict)
    compliance_reviewed: bool = False
    schedule: str = "0 9 * * *"


class Skill03Config(SkillItemConfig):
    default_blog_handle: str = "news"
    article_length_min: int = 1500
    article_length_max: int = 3000
    auto_publish: bool = True
    schedule: str = "0 6 * * 1,3,5"


class Skill04Config(SkillItemConfig):
    abandoned_cart_check_interval_minutes: int = 15
    abandoned_cart_sequence: list[dict] = Field(default_factory=list)
    sms_enabled: bool = False
    schedule: str = ""


class Skill05Config(SkillItemConfig):
    daily_report_time: str = "08:00"
    weekly_report_day: int = 1
    weekly_report_time: str = "09:00"
    default_cogs_margin: float = 0.40
    output_destinations: list[str] = Field(default_factory=lambda: ["csv"])
    schedule: str = ""


class SkillsConfig(BaseModel):
    skill_01_product_listing: Skill01Config = Field(default_factory=Skill01Config)
    skill_02_product_reviews: Skill02Config = Field(default_factory=Skill02Config)
    skill_03_blog_content: Skill03Config = Field(default_factory=Skill03Config)
    skill_04_customer_notification: Skill04Config = Field(default_factory=Skill04Config)
    skill_05_revenue_calculation: Skill05Config = Field(default_factory=Skill05Config)


class AppConfig(BaseModel):
    woocommerce: WooCommerceConfig | None = None
    wordpress: WordPressConfig | None = None
    shopify: ShopifyConfig | None = None
    store_info: StoreInfoConfig = Field(default_factory=StoreInfoConfig)
    content_rules: ContentRulesConfig = Field(default_factory=ContentRulesConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    env: dict[str, str | None] = Field(default_factory=dict)


# --- Loader ---

_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(value: Any, env_map: dict[str, str]) -> Any:
    """Recursively resolve ${VAR_NAME} references in YAML values."""
    if isinstance(value, str):
        def _replacer(m: re.Match) -> str:
            var_name = m.group(1)
            resolved = env_map.get(var_name, "")
            if not resolved:
                raise MissingApiKeyError(
                    f"Environment variable '{var_name}' is referenced in config "
                    f"but not set in .env"
                )
            return resolved
        return _VAR_PATTERN.sub(_replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v, env_map) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item, env_map) for item in value]
    return value


def load_config(
    env_path: str | Path | None = None,
    store_yaml: str | Path | None = None,
    content_rules_yaml: str | Path | None = None,
    skills_yaml: str | Path | None = None,
) -> AppConfig:
    """
    Load configuration from .env and YAML files, validate with Pydantic.

    Resolution order:
    1. Load .env into process environment and env_map
    2. Load YAML files with ${VAR} placeholders resolved
    3. Merge into a single dict
    4. Validate with Pydantic AppConfig
    """
    env_path = Path(env_path) if env_path else _PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)

    env_map = {k: v for k, v in os.environ.items()}

    # Load and resolve YAML files
    store_path = Path(store_yaml) if store_yaml else _CONFIG_DIR / "store.yaml"
    content_path = (
        Path(content_rules_yaml) if content_rules_yaml else _CONFIG_DIR / "content_rules.yaml"
    )
    skills_path = Path(skills_yaml) if skills_yaml else _CONFIG_DIR / "skills.yaml"

    def _load_yaml(path: Path) -> dict:
        if not path.exists():
            raise InvalidConfigError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return _resolve_env_vars(raw, env_map)

    store_data = _load_yaml(store_path)
    content_data = _load_yaml(content_path)
    skills_data = _load_yaml(skills_path)

    # Build merged config dict
    merged = {
        "woocommerce": store_data.get("woocommerce"),
        "wordpress": store_data.get("wordpress"),
        "shopify": store_data.get("shopify"),
        "store_info": store_data.get("store_info", {}),
        "content_rules": content_data,
        "skills": skills_data.get("skills", {}),
        "env": env_map,
    }

    try:
        return AppConfig(**merged)
    except ValidationError as e:
        raise InvalidConfigError(f"Config validation failed:\n{e}") from e


def _load_config_singleton() -> AppConfig:
    """Load config once and cache it."""
    if not hasattr(_load_config_singleton, "_cache"):
        _load_config_singleton._cache = load_config()
    return _load_config_singleton._cache
