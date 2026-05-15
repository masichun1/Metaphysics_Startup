"""Skill 04 — WooCommerce 客户通知 (Customer Notification)

订单确认邮件 + 弃单检测 + 折扣券挽回
"""
import json, logging, random, string, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.logger import get_logger
from core.woocommerce_client import WooCommerceClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_04_customer_notification.email_sender import EmailSender

logger = get_logger("metaphysics.wp_skill_04")
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


class Skill04WPNotifications(BaseSkill):
    skill_id = "wp_skill_04"
    skill_name = "WooCommerce Notifications"

    def __init__(self, config: AppConfig, wc: WooCommerceClient, ai: AIClient):
        super().__init__(config, wc, ai)
        self.wc = wc
        env_map = config.env
        self.email = EmailSender(
            smtp_host=env_map.get("SMTP_HOST", ""), smtp_port=int(env_map.get("SMTP_PORT", "587")),
            smtp_user=env_map.get("SMTP_USER", ""), smtp_password=env_map.get("SMTP_PASSWORD", ""),
            from_email=env_map.get("FROM_EMAIL", ""), from_name=env_map.get("FROM_NAME", "Mystic Sanctuary"),
        )

    def run(self, dry_run: bool = False, **kwargs) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        # 1. Check for new orders needing confirmation
        try:
            recent_orders = self.wc.get_orders(per_page=50, status="processing")
            for order in recent_orders:
                billing = order.get("billing", {})
                email_to = billing.get("email", "")
                if email_to and order.get("status") == "processing":
                    if not dry_run:
                        self._send_order_confirmation(order, email_to)
                    result.items_processed += 1
                    result.items_succeeded += 1
                    self.log.info("order_email_sent", order_id=order.get("id"), email=email_to)
        except Exception as e:
            result.errors.append(SkillErrorDetail(message=f"Order notification failed: {e}"))

        # 2. Generate abandoned cart recovery coupons
        try:
            result = self._handle_abandoned_cart_recovery(result, dry_run)
        except Exception as e:
            result.warnings.append(f"Cart recovery: {e}")

        return result

    def _send_order_confirmation(self, order: dict, email_to: str) -> None:
        """Send a warm order confirmation email."""
        items_html = "<br>".join(
            f"• {item.get('name', 'Item')} x{item.get('quantity', 1)} — ${item.get('total', '0')}"
            for item in order.get("line_items", [])
        )
        self.email.send(
            to_email=email_to,
            subject=f"Order #{order.get('id')} Confirmed — Mystic Sanctuary",
            html_body=f"""<h2>Thank You for Your Order!</h2>
<p>Your order <strong>#{order.get('id')}</strong> has been received and is being prepared with care.</p>
<p>{items_html}</p>
<p><strong>Total: ${order.get('total', '0')}</strong></p>
<p>We'll notify you when your order ships.</p>
<p style='color:#6b4e7e;'><em>May these sacred tools bring light to your journey.</em></p>
<p>— Mystic Sanctuary</p>""",
        )

    def _handle_abandoned_cart_recovery(self, result: SkillResult, dry_run: bool) -> SkillResult:
        """Generate discount coupons for abandoned cart recovery emails."""
        coupons = self.wc.get_coupons()
        if len(coupons) >= 5:  # Don't create too many
            return result

        code = f"COSMIC{random.randint(10, 99)}"
        if not dry_run:
            coupon_data = {
                "code": code, "discount_type": "percent",
                "amount": "10", "individual_use": True,
                "description": "Abandoned cart recovery — 10% off", "usage_limit": 1,
            }
            self.wc.create_coupon(coupon_data)
        result.metadata["recovery_coupon"] = code
        self.log.info("coupon_created", code=code)
        return result
