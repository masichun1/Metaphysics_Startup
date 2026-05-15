"""Abandoned cart detection and recovery logic for Shopify."""

import logging
from core.logger import get_logger
from datetime import datetime, timedelta, timezone
from typing import Any

from core.shopify_client import ShopifyClient

logger = get_logger("metaphysics.skill_04")


class AbandonedCartDetector:
    """Detect abandoned checkouts and prepare recovery email data."""

    def __init__(self, shopify_client: ShopifyClient):
        self.shopify = shopify_client

    def get_abandoned_carts(
        self,
        lookback_hours: int = 24,
        exclude_contacted: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch abandoned checkouts from the past N hours.

        Returns list of dicts with customer email, name, cart items, and cart URL.
        """
        now = datetime.now(timezone.utc)
        created_at_min = (now - timedelta(hours=lookback_hours)).isoformat()
        created_at_max = now.isoformat()

        try:
            checkouts = self.shopify.get_abandoned_checkouts(
                created_at_min=created_at_min,
                created_at_max=created_at_max,
            )
        except Exception as e:
            logger.error("fetch_abandoned_carts_failed", error=str(e))
            return []

        excluded = exclude_contacted or set()
        results = []

        for checkout in checkouts:
            email = (checkout.get("email") or "").strip()
            if not email:
                continue
            if email in excluded:
                continue

            results.append({
                "email": email,
                "name": checkout.get("shipping_address", {}).get("first_name", "") or "",
                "cart_token": checkout.get("token", ""),
                "cart_url": checkout.get("abandoned_checkout_url", ""),
                "created_at": checkout.get("created_at", ""),
                "line_items": [
                    {
                        "title": item.get("title", ""),
                        "quantity": item.get("quantity", 1),
                        "price": item.get("price", "0"),
                    }
                    for item in checkout.get("line_items", [])
                ],
                "total_price": checkout.get("total_price", "0"),
                "currency": checkout.get("currency", "USD"),
            })

        logger.info("abandoned_carts_found", count=len(results), lookback_h=lookback_hours)
        return results
