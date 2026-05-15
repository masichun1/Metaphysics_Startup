#!/usr/bin/env python3
"""Metaphysics Startup — 跨境业务主入口调度器

Usage:
    python main.py run skill_01 [--dry-run] [--csv-path PATH]
    python main.py run skill_02 [--dry-run]
    python main.py run skill_03 [--dry-run] [--topic TOPIC]
    python main.py run skill_04 [--dry-run]
    python main.py run skill_05 [--dry-run] [--report-type daily|weekly]
    python main.py run-all [--dry-run]
    python main.py schedule  # Start cron-based scheduler
"""

import argparse
import logging
from core.logger import get_logger
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config_loader import load_config, _load_config_singleton
from core.logger import setup_logging, get_logger
from core.shopify_client import ShopifyClient
from core.ai_client import AIClient
from core.exceptions import MetaphysicsException

logger = get_logger("metaphysics.main")


def create_clients(config):
    """Initialize shared clients."""
    shopify = ShopifyClient(config.shopify)
    ai = AIClient(config)
    return shopify, ai


def run_skill(skill_id: str, config, shopify, ai, dry_run: bool = False, **kwargs):
    """Run a single skill by ID."""
    skills_map = {
        "skill_01": ("skills.skill_01_product_listing.main", "Skill01ProductListing"),
        "skill_02": ("skills.skill_02_product_reviews.main", "Skill02ProductReviews"),
        "skill_03": ("skills.skill_03_blog_content.main", "Skill03BlogContent"),
        "skill_04": ("skills.skill_04_customer_notification.main", "Skill04CustomerNotification"),
        "skill_05": ("skills.skill_05_revenue_calculation.main", "Skill05RevenueCalculation"),
    }

    if skill_id not in skills_map:
        available = ", ".join(skills_map.keys())
        print(f"Unknown skill '{skill_id}'. Available: {available}")
        sys.exit(1)

    module_path, class_name = skills_map[skill_id]
    import importlib
    module = importlib.import_module(module_path)
    skill_class = getattr(module, class_name)
    skill = skill_class(config, shopify, ai)

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
    run_parser.add_argument("skill", help="Skill ID (skill_01 through skill_05)")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    run_parser.add_argument("--csv-path", help="Path to CSV for skill_01")
    run_parser.add_argument("--topic", help="Blog topic for skill_03")
    run_parser.add_argument("--report-type", default="daily", choices=["daily", "weekly"])
    run_parser.add_argument("--start-date", help="Start date for skill_05 (ISO format)")
    run_parser.add_argument("--end-date", help="End date for skill_05 (ISO format)")

    # --- run-all ---
    all_parser = sub.add_parser("run-all", help="Run all enabled skills")
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

    shopify, ai = create_clients(config)

    try:
        if args.command == "run":
            kwargs = {}
            if hasattr(args, "csv_path") and args.csv_path:
                kwargs["csv_path"] = args.csv_path
            if hasattr(args, "topic") and args.topic:
                kwargs["topic"] = args.topic
            if hasattr(args, "report_type"):
                kwargs["report_type"] = args.report_type
            if hasattr(args, "start_date") and args.start_date:
                kwargs["start_date"] = args.start_date
            if hasattr(args, "end_date") and args.end_date:
                kwargs["end_date"] = args.end_date

            result = run_skill(args.skill, config, shopify, ai, dry_run=args.dry_run, **kwargs)
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
            print(f"{'='*50}\n")

        elif args.command == "run-all":
            all_skills = ["skill_01", "skill_02", "skill_03", "skill_04", "skill_05"]
            skip = set(args.skip or [])
            for sid in all_skills:
                if sid in skip:
                    print(f"Skipping {sid}")
                    continue
                print(f"\n>>> Running {sid}...")
                try:
                    result = run_skill(sid, config, shopify, ai, dry_run=args.dry_run)
                    print(f"    {result.status}: {result.items_succeeded}/{result.items_processed} in {result.duration_seconds:.1f}s")
                except Exception as e:
                    print(f"    FAILED: {e}")

    finally:
        shopify.close()


if __name__ == "__main__":
    main()
