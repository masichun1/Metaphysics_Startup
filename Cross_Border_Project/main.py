#!/usr/bin/env python3
"""Metaphysics Startup — 跨境业务主入口调度器

Usage:
  # WooCommerce Skills (推荐)
  python main.py run wp_skill_01 [--dry-run] [--csv-path PATH]
  python main.py run wp_skill_02 [--dry-run]
  python main.py run wp_skill_03 [--dry-run] [--topic TOPIC]
  python main.py run wp_skill_04 [--dry-run]
  python main.py run wp_skill_05 [--dry-run] [--report-type daily|weekly]
  python main.py run wp_skill_06 [--dry-run] [--effect EFFECT]
  python main.py run-wp-all [--dry-run]

  # Legacy Shopify Skills
  python main.py run skill_01 [--dry-run] [--csv-path PATH]
  python main.py run-all [--dry-run]
"""

import argparse
import json
import logging
from core.logger import get_logger
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config_loader import load_config
from core.logger import setup_logging, get_logger
from core.shopify_client import ShopifyClient
from core.woocommerce_client import WooCommerceClient, WordPressClient
from core.ai_client import AIClient
from core.exceptions import MetaphysicsException

logger = get_logger("metaphysics.main")


def create_clients(config):
    """Initialize shared clients for all platforms."""
    ai = AIClient(config)
    wc = None
    wp = None
    shopify = None

    if config.woocommerce:
        wc = WooCommerceClient(
            site_url=config.woocommerce.site_url,
            consumer_key=config.woocommerce.consumer_key,
            consumer_secret=config.woocommerce.consumer_secret,
        )
    if config.wordpress and config.wordpress.username:
        wp = WordPressClient(
            site_url=config.wordpress.site_url,
            username=config.wordpress.username,
            app_password=config.wordpress.app_password,
        )
    if config.shopify and config.shopify.domain:
        shopify = ShopifyClient(config.shopify)

    return ai, wc, wp, shopify


def run_skill(skill_id: str, config, ai, wc, wp, shopify, dry_run: bool = False, **kwargs):
    """Run a single skill by ID."""
    # WooCommerce Skills
    wp_skills_map = {
        "wp_skill_01": ("skills.skill_01_wp_product_listing.main", "Skill01WPProductListing", "wc"),
        "wp_skill_02": ("skills.skill_02_wp_reviews.main", "Skill02WPReviews", "wc"),
        "wp_skill_03": ("skills.skill_03_wp_blog.main", "Skill03WPBlog", "wp"),
        "wp_skill_04": ("skills.skill_04_wp_notifications.main", "Skill04WPNotifications", "wc"),
        "wp_skill_05": ("skills.skill_05_wp_revenue.main", "Skill05WPRevenue", "wc"),
        "wp_skill_06": ("skills.skill_06_wp_customization.main", "Skill06WPCustomization", "wp"),
    }
    # Legacy Shopify Skills
    shopify_skills_map = {
        "skill_01": ("skills.skill_01_product_listing.main", "Skill01ProductListing", "shopify"),
        "skill_02": ("skills.skill_02_product_reviews.main", "Skill02ProductReviews", "shopify"),
        "skill_03": ("skills.skill_03_blog_content.main", "Skill03BlogContent", "shopify"),
        "skill_04": ("skills.skill_04_customer_notification.main", "Skill04CustomerNotification", "shopify"),
        "skill_05": ("skills.skill_05_revenue_calculation.main", "Skill05RevenueCalculation", "shopify"),
    }

    skills_map = {**wp_skills_map, **shopify_skills_map}

    if skill_id not in skills_map:
        available = ", ".join(skills_map.keys())
        print(f"Unknown skill '{skill_id}'. Available: {available}")
        sys.exit(1)

    module_path, class_name, client_type = skills_map[skill_id]
    import importlib
    module = importlib.import_module(module_path)
    skill_class = getattr(module, class_name)

    # Instantiate skill with the correct client
    if client_type == "wc":
        skill = skill_class(config, wc, ai)
    elif client_type == "wp":
        skill = skill_class(config, wp, ai)
    elif client_type == "shopify":
        skill = skill_class(config, shopify, ai)
    else:
        skill = skill_class(config, None, ai)

    result = skill.execute(dry_run=dry_run, **kwargs)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Metaphysics Cross-Border Automation Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run skill_01 --dry-run
  python main.py run skill_01 --csv-path data/product_imports/products.csv
  python main.py run skill_03 --topic "Crystals for Beginners"
  python main.py run skill_05 --report-type weekly
  python main.py run-all --dry-run
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_parser = sub.add_parser("run", help="Run a single skill")
    run_parser.add_argument("skill", help="Skill ID (wp_skill_01~06 or skill_01~05)")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    run_parser.add_argument("--csv-path", help="Path to CSV for product listing")
    run_parser.add_argument("--topic", help="Blog topic for wp_skill_03")
    run_parser.add_argument("--effect", help="Effect name for wp_skill_06")
    run_parser.add_argument("--report-type", default="daily", choices=["daily", "weekly"])
    run_parser.add_argument("--start-date", help="Start date for revenue (ISO format)")
    run_parser.add_argument("--end-date", help="End date for revenue (ISO format)")

    # --- run-wp-all ---
    wp_all_parser = sub.add_parser("run-wp-all", help="Run all WooCommerce skills")
    wp_all_parser.add_argument("--dry-run", action="store_true", help="Preview all skills")
    wp_all_parser.add_argument("--skip", nargs="+", default=[], help="Skill IDs to skip")

    # --- run-all ---
    all_parser = sub.add_parser("run-all", help="Run all legacy Shopify skills")
    all_parser.add_argument("--dry-run", action="store_true", help="Preview all skills")
    all_parser.add_argument("--skip", nargs="+", default=[], help="Skill IDs to skip")

    # --- schedule ---
    sub.add_parser("schedule", help="Start cron-based scheduler")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Load environment
    load_dotenv()

    try:
        config = load_config()
    except MetaphysicsException as e:
        print(f"Config error: {e}")
        sys.exit(1)

    setup_logging(level=config.env.get("LOG_LEVEL", "INFO"))
    logger = get_logger()

    if args.command == "schedule":
        print("Starting cron scheduler... (not yet implemented — coming soon)")
        return

    ai, wc, wp, shopify = create_clients(config)

    try:
        if args.command == "run":
            kwargs = {}
            if hasattr(args, "csv_path") and args.csv_path:
                kwargs["csv_path"] = args.csv_path
            if hasattr(args, "topic") and args.topic:
                kwargs["topic"] = args.topic
            if hasattr(args, "effect") and args.effect:
                kwargs["effect"] = args.effect
            if hasattr(args, "report_type"):
                kwargs["report_type"] = args.report_type
            if hasattr(args, "start_date") and args.start_date:
                kwargs["start_date"] = args.start_date
            if hasattr(args, "end_date") and args.end_date:
                kwargs["end_date"] = args.end_date

            result = run_skill(args.skill, config, ai, wc, wp, shopify, dry_run=args.dry_run, **kwargs)
            _print_result(result)

        elif args.command == "run-all":
            all_skills = ["skill_01", "skill_02", "skill_03", "skill_04", "skill_05"]
            skip = set(args.skip or [])
            for sid in all_skills:
                if sid in skip:
                    print(f"Skipping {sid}")
                    continue
                print(f"\n>>> Running {sid}...")
                try:
                    result = run_skill(sid, config, ai, wc, wp, shopify, dry_run=args.dry_run)
                    print(f"    {result.status}: {result.items_succeeded}/{result.items_processed} in {result.duration_seconds:.1f}s")
                except Exception as e:
                    print(f"    FAILED: {e}")

        elif args.command == "run-wp-all":
            wp_skills = ["wp_skill_01", "wp_skill_02", "wp_skill_03", "wp_skill_04", "wp_skill_05", "wp_skill_06"]
            skip = set(args.skip or [])
            for sid in wp_skills:
                if sid in skip:
                    print(f"Skipping {sid}")
                    continue
                print(f"\n>>> Running {sid}...")
                try:
                    result = run_skill(sid, config, ai, wc, wp, shopify, dry_run=args.dry_run)
                    print(f"    {result.status}: {result.items_succeeded}/{result.items_processed} in {result.duration_seconds:.1f}s")
                except Exception as e:
                    print(f"    FAILED: {e}")

    finally:
        if wc:
            wc.close()
        if wp:
            wp.close()
        if shopify:
            shopify.close()


def _print_result(result):
    print(f"\n{'='*50}")
    print(f"Skill: {result.skill_id} ({result.status})")
    print(f"Processed: {result.items_processed} | Succeeded: {result.items_succeeded} | Failed: {result.items_failed}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for e in result.errors[:5]:
            print(f"  - [{e.item_id}] {e.message}")
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for w in result.warnings[:5]:
            print(f"  - {w}")
    if result.metadata:
        print(f"\nMetadata: {json.dumps({k: str(v) for k, v in result.metadata.items()}, indent=2)}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
