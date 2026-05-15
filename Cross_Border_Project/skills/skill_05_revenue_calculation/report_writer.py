"""Report generation — CSV and Slack output for revenue reports."""

import csv
import logging
from core.logger import get_logger
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = get_logger("metaphysics.skill_05")

_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"


class ReportWriter:
    """Write revenue reports to CSV files and optionally push to Slack."""

    def __init__(self, slack_bot_token: str = "", slack_channel: str = "#reports"):
        self.slack_token = slack_bot_token
        self.slack_channel = slack_channel

    def write_csv(self, report_data: dict, report_type: str = "daily") -> Path:
        """Write a revenue report to CSV. Returns the file path."""
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"revenue_{report_type}_{ts}.csv"
        filepath = _REPORTS_DIR / filename

        # Flatten the report dict for CSV
        rows = []
        if "metrics" in report_data:
            rows.append(report_data["metrics"])
        if "top_products" in report_data:
            rows.extend(report_data["top_products"])
        if "ad_spend" in report_data:
            rows.append(report_data["ad_spend"])

        if rows:
            fieldnames = list(rows[0].keys())
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        logger.info("report_csv_written", path=str(filepath))
        return filepath

    def send_slack(self, report_data: dict, report_type: str = "daily") -> bool:
        """Push a summary report to Slack. Returns True on success."""
        if not self.slack_token:
            logger.info("slack_not_configured")
            return False

        summary = self._format_slack_summary(report_data, report_type)

        try:
            response = httpx.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.slack_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "channel": self.slack_channel,
                    "text": summary,
                    "mrkdwn": True,
                },
                timeout=15,
            )
            result = response.json()
            if result.get("ok"):
                logger.info("slack_report_sent", channel=self.slack_channel)
                return True
            else:
                logger.error("slack_send_error", error=result.get("error", "unknown"))
                return False
        except Exception as e:
            logger.error("slack_send_exception", error=str(e))
            return False

    @staticmethod
    def _format_slack_summary(data: dict, report_type: str) -> str:
        """Format report data as a Slack mrkdwn message."""
        metrics = data.get("metrics", {})
        ad_spend = data.get("ad_spend", {})

        lines = [
            f":crystal_ball: *Mystic Sanctuary — {report_type.title()} Revenue Report*",
            f"",
            f"*Summary*",
            f"• GMV: `${metrics.get('gmv', 0):,.2f}`",
            f"• Net Revenue: `${metrics.get('net_revenue', 0):,.2f}`",
            f"• COGS: `${metrics.get('cogs', 0):,.2f}`",
            f"• Ad Spend: `${ad_spend.get('total_ad_spend', 0):,.2f}`",
            f"• Net Profit: `${metrics.get('net_profit', 0):,.2f}`",
            f"• Profit Margin: `{metrics.get('profit_margin_pct', 0):.1f}%`",
            f"• ROAS: `{metrics.get('roas', 0):.2f}x`",
            f"• Orders: `{metrics.get('total_orders', 0)}`",
            f"• AOV: `${metrics.get('aov', 0):,.2f}`",
        ]

        platform_breakdown = []
        for key, value in ad_spend.items():
            if key.startswith("meta_"):
                platform_breakdown.append(f"• Meta Ads: `${value:,.2f}`")
            elif key.startswith("google_"):
                platform_breakdown.append(f"• Google Ads: `${value:,.2f}`")
            elif key.startswith("tiktok_"):
                platform_breakdown.append(f"• TikTok Ads: `${value:,.2f}`")

        if platform_breakdown:
            lines.append(f"")
            lines.append(f"*Platform Breakdown*")
            lines.extend(platform_breakdown)

        lines.append(f"")
        lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

        return "\n".join(lines)
