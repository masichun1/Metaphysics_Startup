"""Skill 05 — WooCommerce 收益计算 (Revenue Calculation)

WooCommerce 订单数据 + 广告支出 → 利润报表 (CSV + Slack)
"""
import json, logging, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.logger import get_logger
from core.woocommerce_client import WooCommerceClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_05_revenue_calculation.ad_platforms import AdPlatformClient
from skills.skill_05_revenue_calculation.report_writer import ReportWriter

logger = get_logger("metaphysics.wp_skill_05")
_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"


class Skill05WPRevenue(BaseSkill):
    skill_id = "wp_skill_05"
    skill_name = "WooCommerce Revenue"

    def __init__(self, config: AppConfig, wc: WooCommerceClient, ai: AIClient):
        super().__init__(config, wc, ai)
        self.wc = wc
        env_map = config.env
        self.ad_client = AdPlatformClient(env_map)
        self.report_writer = ReportWriter(
            slack_bot_token=env_map.get("SLACK_BOT_TOKEN", ""),
            slack_channel=env_map.get("SLACK_REPORT_CHANNEL", "#reports"),
        )
        self.cogs_margin = getattr(self._get_skill_config(), "default_cogs_margin", 0.40)

    def run(self, dry_run: bool = False, **kwargs) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())
        report_type = kwargs.get("report_type", "daily")

        if report_type == "weekly":
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=7)
        else:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=1)

        start_str = start.isoformat()
        end_str = end.isoformat()

        # Fetch WooCommerce orders
        try:
            orders = self.wc.get_all_orders(after=start_str, before=end_str)
        except Exception as e:
            result.errors.append(SkillErrorDetail(message=str(e)))
            result.status = "failed"
            return result

        # Calculate metrics
        gross_sales = sum(float(o.get("total", 0) or 0) for o in orders)
        total_orders = len(orders)
        total_items = sum(
            sum(item.get("quantity", 0) for item in o.get("line_items", []))
            for o in orders
        )

        ad_spend = self.ad_client.get_all_platforms_spend(start_str, end_str)
        total_ad = ad_spend.get("total_ad_spend", 0.0)
        cogs = gross_sales * self.cogs_margin
        net_profit = gross_sales - cogs - total_ad
        margin = (net_profit / gross_sales * 100) if gross_sales > 0 else 0.0
        roas = (gross_sales / total_ad) if total_ad > 0 else float("inf")

        report = {
            "report_type": report_type, "period_start": start_str, "period_end": end_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "gmv": round(gross_sales, 2), "cogs": round(cogs, 2),
                "net_profit": round(net_profit, 2), "profit_margin_pct": round(margin, 2),
                "roas": round(roas, 2) if roas != float("inf") else "N/A",
                "total_orders": total_orders, "total_items_sold": total_items,
                "aov": round(gross_sales / total_orders, 2) if total_orders > 0 else 0.0,
            },
            "ad_spend": ad_spend,
        }

        if dry_run:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = _REPORTS_DIR / f"wp_skill_05_{report_type}_{ts}.json"
            _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            result.metadata["export"] = str(path)
        else:
            self.report_writer.write_csv(report, report_type)
            self.report_writer.send_slack(report, report_type)

        result.items_succeeded = 1
        result.metadata["net_profit"] = round(net_profit, 2)
        return result
