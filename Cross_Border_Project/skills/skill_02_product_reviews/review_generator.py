"""Generate authentic-feeling English product reviews with AI and persona-based variation."""

import logging
from core.logger import get_logger
import random
from typing import Any

from core.ai_client import AIClient
from skills.skill_02_product_reviews.personas import PERSONA_POOL

logger = get_logger("metaphysics.skill_02")


class ReviewGenerator:
    """Generate diverse, realistic product reviews using Claude API."""

    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def generate_for_product(
        self,
        product_info: dict,
        target_rating: int | None = None,
        count: int = 3,
    ) -> list[dict]:
        """Generate `count` reviews for a single product.

        Args:
            product_info: Dict with title, category, price, etc.
            target_rating: Optional specific star rating. If None, follows distribution.
            count: Number of reviews to generate.

        Returns:
            List of review dicts ready for import.
        """
        reviews = []
        used_persona_indices: set[int] = set()

        for _ in range(count):
            persona = self._pick_persona(used_persona_indices)
            used_persona_indices.add(id(persona))

            rating = target_rating if target_rating else self._pick_rating()

            try:
                review = self.ai.generate_review(
                    product_info=product_info,
                    persona={**persona, "target_rating": rating},
                )
                review["product_title"] = product_info.get("title", "")
                review["verified_purchase"] = True
                review["created_at"] = None  # Will be set by Shopify on import
                reviews.append(review)
            except Exception as e:
                logger.error(
                    "review_generation_failed",
                    product=product_info.get("title", "unknown"),
                    persona=persona.get("name"),
                    error=str(e),
                )

        return reviews

    @staticmethod
    def _pick_persona(used: set[int]) -> dict:
        available = [p for p in PERSONA_POOL if id(p) not in used]
        if not available:
            available = PERSONA_POOL
        return random.choice(available)

    @staticmethod
    def _pick_rating() -> int:
        """Weighted random rating matching config distribution targets."""
        weights = {5: 50, 4: 25, 3: 15, 2: 7, 1: 3}
        population = list(weights.keys())
        weight_values = list(weights.values())
        return random.choices(population, weights=weight_values, k=1)[0]
