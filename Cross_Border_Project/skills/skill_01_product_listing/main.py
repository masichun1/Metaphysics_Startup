import json
import logging
from core.logger import get_logger
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.shopify_client import ShopifyClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_01_product_listing.csv_importer import CsvImporter, RawProductInput
from skills.skill_01_product_listing.image_handler import ImageHandler
from skills.skill_01_product_listing.product_generator import ProductGenerator

logger = get_logger("metaphysics.skill_01")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill01ProductListing(BaseSkill):
    """
    Skill 01: Product Listing Automation.

    Flow: CSV parse -> AI generate English content -> upload images -> create/update in Shopify.
    """

    skill_id = "skill_01"
    skill_name = "Product Listing"

    def __init__(
        self,
        config: AppConfig,
        shopify_client: ShopifyClient,
        ai_client: AIClient,
    ):
        super().__init__(config, shopify_client, ai_client)
        self.generator = ProductGenerator(ai_client)
        skill_cfg = self._get_skill_config()
        self.batch_size = getattr(skill_cfg, "batch_size", 5)
        self.upsert_mode = getattr(skill_cfg, "upsert_mode", True)
        img_cfg = getattr(skill_cfg, "image", None)
        max_dims = (2048, 2048)
        timeout = 30
        if img_cfg:
            max_dims = tuple(img_cfg.get("max_image_dimensions", [2048, 2048]))
            timeout = img_cfg.get("download_timeout_seconds", 30)
        self.image_handler = ImageHandler(
            shopify_client, download_timeout=timeout, max_dimensions=max_dims
        )

    def run(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        csv_path = kwargs.get("csv_path")
        if not csv_path:
            # Scan data/product_imports/ for CSV files
            import_dir = (
                Path(__file__).resolve().parent.parent.parent
                / "data" / "product_imports"
            )
            csv_files = sorted(import_dir.glob("*.csv"))
            if not csv_files:
                return SkillResult(
                    skill_id=self.skill_id,
                    run_id=self.generate_run_id(),
                    status="failed",
                    errors=[
                        SkillErrorDetail(
                            message="No CSV path provided and no CSVs found in data/product_imports/"
                        )
                    ],
                )
            csv_path = str(csv_files[0])

        items = CsvImporter(csv_path).parse()
        if not items:
            return SkillResult(
                skill_id=self.skill_id,
                run_id=self.generate_run_id(),
                status="failed",
                errors=[SkillErrorDetail(message=f"No valid products found in {csv_path}")],
            )

        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())
        generated_products: list[dict] = []

        # Process in batches
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            for item in batch:
                result.items_processed += 1
                try:
                    payload = self.generator.generate(item)
                    if payload is None:
                        result.items_failed += 1
                        result.errors.append(
                            SkillErrorDetail(
                                item_id=item.sku,
                                message="AI generation failed",
                            )
                        )
                        continue

                    if dry_run:
                        generated_products.append(payload)
                        result.items_succeeded += 1
                        self.log.info(
                            "dry_run_product", sku=item.sku, title=payload.get("title", "")
                        )
                        continue

                    # Upsert: check if SKU exists
                    if self.upsert_mode:
                        existing = self.shopify.get_product_by_sku(item.sku)
                        if existing:
                            product_id_str = existing.get("id", "")
                            if product_id_str:
                                # Extract numeric ID from GID
                                product_id = int(str(product_id_str).replace("gid://shopify/Product/", ""))
                                updated = self.shopify.update_product(product_id, payload)
                                self.log.info("product_updated", sku=item.sku, product_id=product_id)
                                result.items_succeeded += 1
                                # Upload images
                                image_urls = item.get_image_urls()
                                if image_urls:
                                    self.image_handler.process_images(product_id, image_urls)
                                continue

                    # Create new product
                    created = self.shopify.create_product(payload)
                    product_id = created.get("id")
                    if product_id:
                        self.log.info("product_created", sku=item.sku, product_id=product_id)
                        result.items_succeeded += 1
                        # Upload images
                        image_urls = item.get_image_urls()
                        if image_urls:
                            self.image_handler.process_images(product_id, image_urls)
                    else:
                        result.items_failed += 1
                        result.errors.append(
                            SkillErrorDetail(
                                item_id=item.sku,
                                message="Shopify API returned no product ID",
                            )
                        )

                except Exception as e:
                    result.items_failed += 1
                    result.errors.append(
                        SkillErrorDetail(
                            item_id=item.sku,
                            message=str(e),
                            exception_type=type(e).__name__,
                        )
                    )
                    self.log.error("product_failed", sku=item.sku, error=str(e))

        # Save dry-run output for review
        if dry_run and generated_products:
            _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            export_path = _EXPORT_DIR / f"skill_01_dry_run_{ts}.json"
            export_path.write_text(
                json.dumps(generated_products, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            result.metadata["dry_run_export"] = str(export_path)
            result.metadata["products_generated"] = len(generated_products)
            self.log.info("dry_run_exported", path=str(export_path))

        return result
