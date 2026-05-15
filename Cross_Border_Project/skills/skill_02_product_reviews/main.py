"""Skill 02: Product Reviews — generate authentic English reviews for social proof."""

import json
import logging
from core.logger import get_logger
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.shopify_client import ShopifyClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_02_product_reviews.review_generator import ReviewGenerator

logger = get_logger("metaphysics.skill_02")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"

# Shopify does not have a native reviews API — reviews are managed by apps like Judge.me or Loox.
# This skill generates reviews and exports them as structured JSON ready for import into
# a third-party review app, or posts them via the review app's API if configured.


class Skill02ProductReviews(BaseSkill):
    """Skill 02: Product Reviews automation."""

    skill_id = "skill_02"
    skill_name = "Product Reviews"

    def __init__(
        self,
        config: AppConfig,
        shopify_client: ShopifyClient,
        ai_client: AIClient,
    ):
        super().__init__(config, shopify_client, ai_client)
        self.generator = ReviewGenerator(ai_client)
        skill_cfg = self._get_skill_config()
        self.reviews_per_product_min = getattr(skill_cfg, "reviews_per_product_min", 3)
        self.reviews_per_product_max = getattr(skill_cfg, "reviews_per_product_max", 7)
        self.daily_max_reviews = getattr(skill_cfg, "daily_max_reviews", 10)

    def run(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        # Fetch products from Shopify
        try:
            products = self.shopify.get_all_products()
        except Exception as e:
            result.errors.append(SkillErrorDetail(
                message=f"Failed to fetch products: {e}",
                exception_type=type(e).__name__,
            ))
            result.status = "failed"
            return result

        if not products:
            result.warnings.append("No products found in Shopify store")
            return result

        all_reviews: list[dict] = []
        total_generated = 0

        for product in products:
            if total_generated >= self.daily_max_reviews:
                result.warnings.append(
                    f"Reached daily max of {self.daily_max_reviews} reviews"
                )
                break

            product_id = product.get("id")
            product_title = product.get("title", "Unknown")

            count = random.randint(self.reviews_per_product_min, self.reviews_per_product_max)
            count = min(count, self.daily_max_reviews - total_generated)

            result.items_processed += 1

            try:
                reviews = self.generator.generate_for_product(
                    product_info={
                        "title": product_title,
                        "category": product.get("product_type", "metaphysical"),
                        "price": product.get("variants", [{}])[0].get("price", "premium"),
                    },
                    count=count,
                )
                for r in reviews:
                    r["product_id"] = product_id
                all_reviews.extend(reviews)
                total_generated += len(reviews)
                result.items_succeeded += 1
                self.log.info(
                    "reviews_generated",
                    product=product_title,
                    count=len(reviews),
                )
            except Exception as e:
                result.items_failed += 1
                result.errors.append(SkillErrorDetail(
                    item_id=str(product_id),
                    message=str(e),
                    exception_type=type(e).__name__,
                ))
                self.log.error("product_review_failed", product=product_title, error=str(e))

        # Export reviews
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_02_reviews_{ts}.json"
        export_path.write_text(
            json.dumps(all_reviews, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        result.metadata["export_path"] = str(export_path)
        result.metadata["total_reviews"] = len(all_reviews)
        result.metadata["dry_run"] = dry_run

        self.log.info(
            "reviews_exported",
            path=str(export_path),
            total=len(all_reviews),
            dry_run=dry_run,
        )

        return result
