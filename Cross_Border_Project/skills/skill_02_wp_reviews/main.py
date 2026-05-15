"""Skill 02 — WooCommerce 产品评论 (Product Reviews)

AI 生成真实感英文 Review → WooCommerce Reviews API
"""
import json, logging, random, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.logger import get_logger
from core.woocommerce_client import WooCommerceClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_02_product_reviews.personas import PERSONA_POOL

logger = get_logger("metaphysics.wp_skill_02")
_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill02WPReviews(BaseSkill):
    skill_id = "wp_skill_02"
    skill_name = "WooCommerce Reviews"

    def __init__(self, config: AppConfig, wc: WooCommerceClient, ai: AIClient):
        super().__init__(config, wc, ai)
        self.wc = wc

    def run(self, dry_run: bool = False, **kwargs) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        try:
            products = self.wc.get_all_products()
        except Exception as e:
            result.errors.append(SkillErrorDetail(message=str(e)))
            result.status = "failed"
            return result

        all_reviews = []
        for product in products[:10]:  # limit per run
            result.items_processed += 1
            persona = random.choice(PERSONA_POOL)
            rating = random.choices([5, 4, 3, 2, 1], weights=[50, 25, 15, 7, 3], k=1)[0]
            try:
                review = self.ai.generate_review(
                    product_info={"title": product.get("name", ""), "category": "metaphysical", "price": product.get("price", "0")},
                    persona={**persona, "target_rating": rating},
                )
                review_data = {
                    "product_id": product["id"],
                    "review": review.get("body", ""),
                    "reviewer": review.get("reviewer_name", persona["name"]),
                    "reviewer_email": f"{persona['name'].lower()}@example.com",
                    "rating": rating,
                    "verified": True,
                }
                if dry_run:
                    all_reviews.append(review_data)
                else:
                    self.wc.create_review(review_data)
                result.items_succeeded += 1
            except Exception as e:
                result.items_failed += 1
                result.errors.append(SkillErrorDetail(item_id=str(product.get("id")), message=str(e)))

        if dry_run and all_reviews:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            export_path = _EXPORT_DIR / f"wp_skill_02_reviews_{ts}.json"
            export_path.write_text(json.dumps(all_reviews, indent=2), encoding="utf-8")
        return result
