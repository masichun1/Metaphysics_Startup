"""Convert Skill 01 export to website product data."""
import json
from pathlib import Path

export = json.loads(
    Path("../data/exports/skill_01_dry_run_20260515_095404.json").read_text(encoding="utf-8")
)

products = []
for p in export:
    variant = p["variants"][0]
    seo_kw = ""
    meta_desc = ""
    for mf in p.get("metafields", []):
        if mf.get("key") == "seo_keywords":
            seo_kw = mf["value"]
        if mf.get("key") == "description_tag":
            meta_desc = mf["value"]

    def clean(text: str) -> str:
        return text.replace("–", "-").replace("—", "-").replace("�", "-")

    products.append({
        "sku": variant["sku"],
        "title": clean(p["title"]),
        "category": p.get("product_type", "Spiritual"),
        "price": float(variant["price"]),
        "compare_at_price": float(variant.get("compare_at_price", 0) or 0),
        "vendor": p.get("vendor", "Mystic Sanctuary"),
        "tags": [t.strip() for t in p.get("tags", "").split(",") if t.strip()],
        "body_html": clean(p.get("body_html", "")),
        "meta_description": clean(meta_desc),
        "seo_keywords": clean(seo_kw),
        "inventory": variant.get("inventory_quantity", 100),
        "image": f"/static/images/{variant['sku'].lower()}.jpg",
    })

Path("data/products.json").write_text(
    json.dumps(products, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"Created {len(products)} products in data/products.json")
for p in products:
    print(f"  - {p['sku']}: {p['title'][:60]} | ${p['price']}")
