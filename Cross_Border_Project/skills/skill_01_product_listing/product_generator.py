import json
import logging
from core.logger import get_logger
from pathlib import Path
from typing import Any

from core.ai_client import AIClient
from skills.skill_01_product_listing.csv_importer import RawProductInput

logger = get_logger("metaphysics.skill_01")

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class ProductGenerator:
    """
    Use AI to generate SEO-optimized English product content from raw input data.

    Generates: English title, HTML description, meta description, SEO keywords, tags.
    """

    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def generate(self, item: RawProductInput) -> dict[str, Any] | None:
        """
        Generate a complete product listing payload for a single product.

        Returns None if generation fails, otherwise a dict ready for Shopify API.
        """
        product_info = {
            "category": item.category,
            "source_title": item.source_title,
            "features": item.features,
            "materials": item.materials,
            "use_case": item.use_case,
            "price": str(item.price),
        }

        try:
            content = self.ai.generate_product_description(product_info)
        except Exception as e:
            logger.error("ai_generation_failed", sku=item.sku, error=str(e))
            return None

        # Build Shopify product payload
        variants_payload = {
            "sku": item.sku,
            "price": str(item.price),
            "inventory_quantity": item.inventory_quantity,
            "requires_shipping": item.requires_shipping,
            "taxable": item.taxable,
            "inventory_management": "shopify",
        }
        if item.compare_at_price and item.compare_at_price > item.price:
            variants_payload["compare_at_price"] = str(item.compare_at_price)

        if item.weight is not None:
            variants_payload["weight"] = item.weight
            variants_payload["weight_unit"] = item.weight_unit

        product_payload: dict[str, Any] = {
            "title": content.get("title", item.source_title),
            "body_html": content.get("body_html", ""),
            "vendor": content.get("vendor", item.vendor),
            "product_type": item.product_type or item.category,
            "tags": ", ".join(content.get("tags", item.get_tags())),
            "variants": [variants_payload],
        }

        # SEO metafields (stored as global metafields on product)
        seo_keywords = content.get("seo_keywords", [])
        meta_description = content.get("meta_description", "")

        product_payload["metafields"] = [
            {
                "namespace": "global",
                "key": "seo_keywords",
                "value": ", ".join(seo_keywords),
                "type": "single_line_text_field",
            },
            {
                "namespace": "global",
                "key": "description_tag",
                "value": meta_description,
                "type": "single_line_text_field",
            },
        ]

        # Store cost price as metafield for Skill 05
        if item.cost is not None:
            product_payload["metafields"].append({
                "namespace": "cost",
                "key": "unit_cost",
                "value": str(item.cost),
                "type": "number_decimal",
            })

        return product_payload

    def generate_batch(self, items: list[RawProductInput]) -> list[dict[str, Any]]:
        """Generate content for a batch of products."""
        results = []
        for item in items:
            payload = self.generate(item)
            if payload:
                results.append(payload)
        return results
