"""Skill 01 — WooCommerce 产品上架 (Product Listing)

CSV → AI 生成英文内容 → WooCommerce REST API 批量上架
"""
import json, logging, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.logger import get_logger
from core.woocommerce_client import WooCommerceClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult

logger = get_logger("metaphysics.wp_skill_01")
_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill01WPProductListing(BaseSkill):
    skill_id = "wp_skill_01"
    skill_name = "WooCommerce Product Listing"

    def __init__(self, config: AppConfig, wc: WooCommerceClient, ai: AIClient):
        super().__init__(config, wc, ai)
        self.wc = wc

    def run(self, dry_run: bool = False, **kwargs) -> SkillResult:
        csv_path = kwargs.get("csv_path")
        if not csv_path:
            import_dir = Path(__file__).resolve().parent.parent.parent / "data" / "product_imports"
            csv_files = sorted(import_dir.glob("*.csv"))
            if not csv_files:
                return SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id(),
                    status="failed", errors=[SkillErrorDetail(message="No CSV found")])
            csv_path = str(csv_files[0])

        from skills.skill_01_product_listing.csv_importer import CsvImporter
        items = CsvImporter(csv_path).parse()
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        for item in items:
            result.items_processed += 1
            try:
                content = self.ai.generate_product_description({
                    "category": item.category, "source_title": item.source_title,
                    "features": item.features, "materials": item.materials,
                    "use_case": item.use_case, "price": str(item.price),
                })
                payload = {
                    "name": content.get("title", item.source_title),
                    "type": "simple",
                    "regular_price": str(item.price),
                    "description": content.get("body_html", ""),
                    "short_description": content.get("meta_description", ""),
                    "sku": item.sku,
                    "categories": [{"name": item.category}],
                    "tags": [{"name": t} for t in content.get("tags", [])],
                    "meta_data": [
                        {"key": "_seo_keywords", "value": ", ".join(content.get("seo_keywords", []))},
                    ],
                    "stock_quantity": item.inventory_quantity,
                    "manage_stock": True,
                }
                if item.compare_at_price and item.compare_at_price > item.price:
                    payload["sale_price"] = str(item.price)
                    payload["regular_price"] = str(item.compare_at_price)

                if dry_run:
                    result.items_succeeded += 1
                    self.log.info("dry_run", sku=item.sku, title=payload["name"])
                else:
                    existing = self.wc.get_product_by_sku(item.sku)
                    if existing:
                        self.wc.update_product(existing["id"], payload)
                        self.log.info("updated", sku=item.sku)
                    else:
                        self.wc.create_product(payload)
                        self.log.info("created", sku=item.sku)
                    result.items_succeeded += 1
            except Exception as e:
                result.items_failed += 1
                result.errors.append(SkillErrorDetail(item_id=item.sku, message=str(e)))

        if dry_run:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            export_path = _EXPORT_DIR / f"wp_skill_01_dry_run_{ts}.json"
            _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        return result
