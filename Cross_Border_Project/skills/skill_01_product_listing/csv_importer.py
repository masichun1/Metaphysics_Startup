import csv
import logging
from core.logger import get_logger
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = get_logger("metaphysics.skill_01")


class RawProductInput(BaseModel):
    """Validated CSV row representing a product to be imported."""
    sku: str = Field(..., min_length=1, description="Unique product SKU")
    source_title: str = Field(..., min_length=1, description="Internal/product reference name")
    category: str = Field(default="Spiritual", description="Product category")
    price: float = Field(gt=0, description="Selling price in USD")
    compare_at_price: float | None = Field(default=None, description="Original/higher price for sale display")
    cost: float | None = Field(default=None, description="Unit cost for COGS calculation")
    vendor: str = Field(default="Mystic Sanctuary")
    product_type: str = Field(default="")
    tags: str = Field(default="", description="Comma-separated tags")
    materials: str = Field(default="")
    features: str = Field(default="")
    use_case: str = Field(default="")
    weight: float | None = None
    weight_unit: str = "lb"
    image_urls: str = Field(default="", description="Pipe-separated image URLs")
    inventory_quantity: int = Field(default=100)
    requires_shipping: bool = True
    taxable: bool = True

    @field_validator("sku")
    @classmethod
    def sku_must_be_clean(cls, v: str) -> str:
        return v.strip()

    def get_image_urls(self) -> list[str]:
        if not self.image_urls:
            return []
        return [u.strip() for u in self.image_urls.split("|") if u.strip()]

    def get_tags(self) -> list[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class CsvImporter:
    """
    Parse and validate product CSV files for import.

    Expected CSV columns:
    sku, source_title, category, price, compare_at_price, cost,
    vendor, product_type, tags, materials, features, use_case,
    weight, image_urls, inventory_quantity
    """

    REQUIRED_COLUMNS = {"sku", "source_title", "price"}

    def __init__(self, csv_path: str | Path):
        self.path = Path(csv_path)
        if not self.path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.path}")

    def parse(self) -> list[RawProductInput]:
        """Parse CSV and return validated product inputs. Skips empty/malformed rows."""
        products: list[RawProductInput] = []
        with open(self.path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row")

            missing = self.REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                raise ValueError(
                    f"CSV missing required columns: {', '.join(sorted(missing))}"
                )

            for row_num, row in enumerate(reader, start=2):
                if not any(v.strip() for v in row.values()):
                    continue
                try:
                    cleaned = {
                        k: (v.strip() if isinstance(v, str) else v)
                        for k, v in row.items()
                    }
                    # Convert numeric fields
                    for field_name in ("price", "compare_at_price", "cost", "weight", "inventory_quantity"):
                        val = cleaned.get(field_name, "")
                        if val == "" or val is None:
                            cleaned[field_name] = None
                        else:
                            try:
                                cleaned[field_name] = float(val) if field_name != "inventory_quantity" else int(float(val))
                            except (ValueError, TypeError):
                                cleaned[field_name] = None

                    # Handle boolean fields
                    for bool_field in ("requires_shipping", "taxable"):
                        val = cleaned.get(bool_field, "true")
                        if isinstance(val, str):
                            cleaned[bool_field] = val.lower() in ("true", "yes", "1")

                    product = RawProductInput(**cleaned)
                    products.append(product)
                except Exception as e:
                    logger.warning("csv_row_parse_error", row=row_num, error=str(e))

        logger.info("csv_parsed", path=str(self.path), product_count=len(products))
        return products
