"""Skill 06 — WordPress 二次开发与定制 (Customization)

生成 PHP/CSS/JS 代码实现：
- 酷炫网页特效 (粒子背景、视差滚动、霓虹灯效)
- WordPress 自定义 Shortcode
- WooCommerce 自定义功能 (结账页定制、产品卡片动效)
- Elementor / Gutenberg 自定义模块
"""
import json, logging, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.logger import get_logger
from core.woocommerce_client import WooCommerceClient, WordPressClient

logger = get_logger("metaphysics.wp_skill_06")
_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"

WP_CUSTOMIZATION_PROMPTS = {
    "product_card_glow": {
        "name": "Product Card Hover Glow Effect",
        "type": "CSS",
        "description": "Products glow with mystical purple/gold aura on hover",
        "prompt": """Write CSS code for WooCommerce product cards with a mystical hover glow effect:
- On hover: purple-to-gold gradient glow shadow around card
- Smooth scale transform (1.03x)
- Gold border appears
- Transition: 0.3s ease
- Use CSS variables for colors
Target: WooCommerce product grid cards (class: .product, .woocommerce ul.products li.product)""",
    },
    "particles_background": {
        "name": "Mystical Particles Background",
        "type": "JavaScript",
        "description": "Floating star/particle animation on homepage",
        "prompt": """Write vanilla JavaScript code that creates a mystical floating particles effect:
- Small glowing dots float upward on the page background
- Colors: gold (#c9a96e) and light purple (#b396c4)
- Particles fade in/out with random opacity
- Canvas-based, performance-optimized (max 50 particles)
- Attached to .hero section
- No external libraries needed""",
    },
    "countdown_timer": {
        "name": "Full Moon Ritual Countdown",
        "type": "Shortcode",
        "description": "WordPress shortcode [moon_countdown] showing time to next full moon",
        "prompt": """Write a WordPress shortcode PHP function [moon_countdown] that:
- Displays countdown to next full moon/new moon
- Shows: days, hours, minutes left
- Styled with mystical gold/purple theme
- Responsive design
- Use wp_remote_get to fetch moon phase data or calculate locally
- Return clean HTML with inline CSS""",
    },
    "woo_checkout_enhance": {
        "name": "WooCommerce Checkout Enhancement",
        "type": "PHP + CSS",
        "description": "Add crystal blessing selection to checkout",
        "prompt": """Write PHP + CSS for a WooCommerce checkout customization:
- Add a dropdown "Choose Your Crystal Blessing" above Place Order button
- Options: Amethyst Protection, Rose Quartz Love, Citrine Abundance, Clear Quartz Clarity
- Free addon, stored as order meta data
- Hook: woocommerce_review_order_before_submit
- CSS: Styled to match mystical theme with purple/gold colors""",
    },
    "newsletter_popup": {
        "name": "Mystical Newsletter Popup",
        "type": "JavaScript + CSS",
        "description": "Exit-intent popup with newsletter signup + 10% discount",
        "prompt": """Write JavaScript + CSS for an exit-intent newsletter popup:
- Triggers when mouse leaves page (exit intent)
- Beautiful mystical design: dark purple overlay, gold border, starry background
- Title: "The Stars Have a Message for You"
- Email input + "Subscribe & Receive 10% Off" button
- 10% discount code = auto-generated WooCommerce coupon
- Cookie: don't show again for 7 days
- CSS: smooth fade-in, responsive, mystical aesthetic""",
    },
}


class Skill06WPCustomization(BaseSkill):
    skill_id = "wp_skill_06"
    skill_name = "WordPress Customization"

    def __init__(self, config: AppConfig, wc: WooCommerceClient | None = None, wp: WordPressClient | None = None, ai: AIClient | None = None):
        super().__init__(config, None, ai)  # type: ignore
        self.wc = wc
        self.wp = wp

    def run(self, dry_run: bool = False, **kwargs) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        effect = kwargs.get("effect", "")
        if effect and effect in WP_CUSTOMIZATION_PROMPTS:
            prompts = {effect: WP_CUSTOMIZATION_PROMPTS[effect]}
        else:
            prompts = WP_CUSTOMIZATION_PROMPTS

        generated = {}
        for key, config in prompts.items():
            result.items_processed += 1
            try:
                code = self.ai.generate_text(
                    user_prompt=f"""You are a WordPress/WooCommerce developer. Write production-ready code for the following customization.

Type: {config['type']}
Name: {config['name']}
Description: {config['description']}

Requirements:
{config['prompt']}

Output ONLY the code with brief comments. Include installation instructions as code comments."""
                )
                generated[key] = {"name": config["name"], "type": config["type"], "code": code}
                result.items_succeeded += 1
                self.log.info("generated", effect=key, name=config["name"])
            except Exception as e:
                result.items_failed += 1
                result.errors.append(SkillErrorDetail(item_id=key, message=str(e)))

        # Export to PHP/CSS/JS files
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = _EXPORT_DIR / f"wp_customization_{ts}"
        out_dir.mkdir(parents=True, exist_ok=True)

        for key, item in generated.items():
            ext_map = {"CSS": "css", "JavaScript": "js", "PHP": "php", "Shortcode": "php", "PHP + CSS": "php"}
            ext = ext_map.get(item["type"], "txt")
            filepath = out_dir / f"{key}.{ext}"
            filepath.write_text(
                f"/**\n * {item['name']}\n * Type: {item['type']}\n * Generated: {ts}\n */\n\n{item['code']}",
                encoding="utf-8",
            )

        # Also create a combined WordPress functions.php snippet
        combined = out_dir / "functions_snippets.php"
        lines = ["<?php\n/**\n * Mystic Sanctuary — Custom Functions\n * Add these snippets to your theme's functions.php\n */\n"]
        for key, item in generated.items():
            if item["type"] in ("PHP", "PHP + CSS", "Shortcode"):
                lines.append(f"\n// === {item['name']} ===\n")
                lines.append(item["code"])
                lines.append("\n")
        combined.write_text("\n".join(lines), encoding="utf-8")

        result.metadata["output_dir"] = str(out_dir)
        result.metadata["effects_generated"] = len(generated)
        self.log.info("exported", dir=str(out_dir), count=len(generated))
        return result
