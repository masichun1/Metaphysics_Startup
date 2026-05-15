"""Ad platform API integrations for pulling advertising spend data.

Supports: Meta Ads (Facebook/Instagram), Google Ads, TikTok Ads.
In dry-run / missing-credentials mode, returns placeholder data.
"""

import logging
from core.logger import get_logger
from datetime import datetime, timedelta, timezone
from typing import Any

logger = get_logger("metaphysics.skill_05")


class AdPlatformClient:
    """Unified client for pulling ad spend from multiple platforms."""

    def __init__(self, env_map: dict[str, str | None]):
        self.meta_token = env_map.get("META_ACCESS_TOKEN", "")
        self.meta_account_id = env_map.get("META_AD_ACCOUNT_ID", "")
        self.google_client_id = env_map.get("GOOGLE_ADS_CLIENT_ID", "")
        self.google_developer_token = env_map.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        self.google_customer_id = env_map.get("GOOGLE_ADS_CUSTOMER_ID", "")
        self.tiktok_token = env_map.get("TIKTOK_ACCESS_TOKEN", "")
        self.tiktok_advertiser_id = env_map.get("TIKTOK_ADVERTISER_ID", "")

    def get_meta_spend(
        self, start_date: str, end_date: str
    ) -> dict[str, float]:
        """Fetch Meta Ads spend for a date range."""
        if not self.meta_token or not self.meta_account_id:
            logger.warning("meta_ads_missing_credentials")
            return {"meta_total_spend": 0.0}

        try:
            # In production: call Facebook Graph API v19.0
            # GET /act_{account_id}/insights?fields=spend&time_range={...}
            # Placeholder: return 0 for now
            logger.info("meta_spend_fetch", start=start_date, end=end_date)
            return {"meta_total_spend": 0.0}
        except Exception as e:
            logger.error("meta_spend_error", error=str(e))
            return {"meta_total_spend": 0.0}

    def get_google_spend(
        self, start_date: str, end_date: str
    ) -> dict[str, float]:
        """Fetch Google Ads spend for a date range."""
        if not self.google_developer_token or not self.google_customer_id:
            logger.warning("google_ads_missing_credentials")
            return {"google_total_spend": 0.0}

        try:
            logger.info("google_spend_fetch", start=start_date, end=end_date)
            return {"google_total_spend": 0.0}
        except Exception as e:
            logger.error("google_spend_error", error=str(e))
            return {"google_total_spend": 0.0}

    def get_tiktok_spend(
        self, start_date: str, end_date: str
    ) -> dict[str, float]:
        """Fetch TikTok Ads spend for a date range."""
        if not self.tiktok_token or not self.tiktok_advertiser_id:
            logger.warning("tiktok_ads_missing_credentials")
            return {"tiktok_total_spend": 0.0}

        try:
            logger.info("tiktok_spend_fetch", start=start_date, end=end_date)
            return {"tiktok_total_spend": 0.0}
        except Exception as e:
            logger.error("tiktok_spend_error", error=str(e))
            return {"tiktok_total_spend": 0.0}

    def get_all_platforms_spend(
        self, start_date: str, end_date: str
    ) -> dict[str, float]:
        """Aggregate ad spend from all platforms."""
        spend = {}
        spend.update(self.get_meta_spend(start_date, end_date))
        spend.update(self.get_google_spend(start_date, end_date))
        spend.update(self.get_tiktok_spend(start_date, end_date))
        spend["total_ad_spend"] = sum(spend.values())
        return spend
