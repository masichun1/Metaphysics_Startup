"""Skill 05: Revenue Calculation — daily/weekly profit reports from Shopify + ad data."""

import json
import logging
from core.logger import get_logger
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.shopify_client import ShopifyClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_05_revenue_calculation.ad_platforms import AdPlatformClient
from skills.skill_05_revenue_calculation.report_writer import ReportWriter

logger = get_logger("metaphysics.skill_05")

_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"


class Skill05RevenueCalculation(BaseSkill):
    """Skill 05: Revenue Calculation automation.

    Flow: fetch Shopify orders -> fetch ad spend -> calculate metrics -> generate report -> output.
    """

    skill_id = "skill_05"
    skill_name = "Revenue Calculation"

    def __init__(
        self,
        config: AppConfig,
        shopify_client: ShopifyClient,
        ai_client: AIClient,
    ):
        super().__init__(config, shopify_client, ai_client)
        skill_cfg = self._get_skill_config()
        self.daily_report_time = getattr(skill_cfg, "daily_report_time", "08:00")
        self.weekly_report_day = getattr(skill_cfg, "weekly_report_day", 1)  # Monday
        self.default_cogs_margin = getattr(skill_cfg, "default_cogs_margin", 0.40)
        self.output_destinations = getattr(skill_cfg, "output_destinations", ["csv", "slack"])

        env_map = config.env
        self.ad_client = AdPlatformClient(env_map)
        self.report_writer = ReportWriter(
            slack_bot_token=env_map.get("SLACK_BOT_TOKEN", ""),
            slack_channel=env_map.get("SLACK_REPORT_CHANNEL", "#reports"),
        )

    def run(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        report_type = kwargs.get("report_type", "daily")  # "daily" or "weekly"
        custom_start = kwargs.get("start_date")
        custom_end = kwargs.get("end_date")

        if custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        elif report_type == "weekly":
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)
        else:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=1)

        start_str = start_date.isoformat() if isinstance(start_date, datetime) else start_date
        end_str = end_date.isoformat() if isinstance(end_date, datetime) else end_date

        self.log.info("revenue_report_start", type=report_type, start=start_str, end=end_str)

        # Step 1: Fetch orders
        try:
            orders = self.shopify.get_all_orders(
                status="any",
                created_at_min=start_str,
                created_at_max=end_str,
            )
        except Exception as e:
            result.errors.append(SkillErrorDetail(message=f"Failed to fetch orders: {e}"))
            result.status = "failed"
            return result

        result.items_processed = len(orders)

        # Step 2: Calculate financial metrics
        metrics = self._calculate_metrics(orders)

        # Step 3: Fetch ad spend
        ad_spend = self.ad_client.get_all_platforms_spend(start_str, end_str)

        # Step 4: Merge and compute final numbers
        total_ad_spend = ad_spend.get("total_ad_spend", 0.0)
        net_revenue = metrics["gross_sales"] - metrics["refunds"] - metrics["shipping_costs"]
        cogs = metrics["gross_sales"] * self.default_cogs_margin
        net_profit = net_revenue - cogs - total_ad_spend
        profit_margin = (net_profit / net_revenue * 100) if net_revenue > 0 else 0.0
        roas = (net_revenue / total_ad_spend) if total_ad_spend > 0 else float("inf")

        report = {
            "report_type": report_type,
            "period_start": start_str,
            "period_end": end_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "gmv": round(metrics["gross_sales"], 2),
                "refunds": round(metrics["refunds"], 2),
                "shipping_costs": round(metrics["shipping_costs"], 2),
                "net_revenue": round(net_revenue, 2),
                "cogs": round(cogs, 2),
                "net_profit": round(net_profit, 2),
                "profit_margin_pct": round(profit_margin, 2),
                "roas": round(roas, 2) if roas != float("inf") else "N/A",
                "total_orders": metrics["total_orders"],
                "total_items_sold": metrics["total_items_sold"],
                "aov": round(metrics["gross_sales"] / metrics["total_orders"], 2) if metrics["total_orders"] > 0 else 0.0,
            },
            "ad_spend": {
                "meta_total_spend": round(ad_spend.get("meta_total_spend", 0.0), 2),
                "google_total_spend": round(ad_spend.get("google_total_spend", 0.0), 2),
                "tiktok_total_spend": round(ad_spend.get("tiktok_total_spend", 0.0), 2),
                "total_ad_spend": round(total_ad_spend, 2),
            },
            "top_products": self._get_top_products(orders, top_n=10),
        }

        # Step 5: Output to configured destinations
        if dry_run:
            # Export report as JSON for inspection
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            export_path = _REPORTS_DIR / f"skill_05_dry_run_{report_type}_{ts}.json"
            _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            result.metadata["dry_run_export"] = str(export_path)
            self.log.info("dry_run_report", path=str(export_path))
        else:
            if "csv" in self.output_destinations:
                csv_path = self.report_writer.write_csv(report, report_type)
                result.metadata["csv_path"] = str(csv_path)
            if "slack" in self.output_destinations:
                self.report_writer.send_slack(report, report_type)

        result.items_succeeded = 1
        result.metadata["report_type"] = report_type
        result.metadata["net_profit"] = round(net_profit, 2)

        self.log.info(
            "revenue_report_complete",
            gmv=round(metrics["gross_sales"], 2),
            net_profit=round(net_profit, 2),
            roas=round(roas, 2) if roas != float("inf") else "N/A",
        )

        return result

    def _calculate_metrics(self, orders: list[dict]) -> dict:
        """Aggregate financial data from Shopify orders."""
        gross_sales = 0.0
        refunds = 0.0
        shipping_costs = 0.0
        total_items = 0

        for order in orders:
            gross_sales += float(order.get("total_price", 0) or 0)

            # Sum refunds
            for refund in order.get("refunds", []):
                for transaction in refund.get("transactions", []):
                    if transaction.get("kind") == "refund":
                        refunds += float(transaction.get("amount", 0) or 0)

            # Shipping
            for shipping_line in order.get("shipping_lines", []):
                shipping_costs += float(shipping_line.get("price", 0) or 0)

            # Count items
            for item in order.get("line_items", []):
                total_items += int(item.get("quantity", 0) or 0)

        return {
            "gross_sales": gross_sales,
            "refunds": refunds,
            "shipping_costs": shipping_costs,
            "total_orders": len(orders),
            "total_items_sold": total_items,
        }

    @staticmethod
    def _get_top_products(orders: list[dict], top_n: int = 10) -> list[dict]:
        """Extract top-selling products by quantity from orders."""
        product_counts: dict[str, dict] = {}

        for order in orders:
            for item in order.get("line_items", []):
                title = item.get("title", "Unknown")
                if title not in product_counts:
                    product_counts[title] = {
                        "product_title": title,
                        "total_quantity": 0,
                        "total_revenue": 0.0,
                    }
                qty = int(item.get("quantity", 0) or 0)
                price = float(item.get("price", 0) or 0)
                product_counts[title]["total_quantity"] += qty
                product_counts[title]["total_revenue"] += price * qty

        sorted_products = sorted(
            product_counts.values(),
            key=lambda x: x["total_quantity"],
            reverse=True,
        )
        return sorted_products[:top_n]
