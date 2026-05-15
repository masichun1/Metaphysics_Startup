"""Skill 04: Customer Notification — abandoned cart recovery and transactional emails."""

import json
import logging
from core.logger import get_logger
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.shopify_client import ShopifyClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_04_customer_notification.abandoned_cart import AbandonedCartDetector
from skills.skill_04_customer_notification.email_sender import EmailSender

logger = get_logger("metaphysics.skill_04")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
_CONTACTED_LOG = _CACHE_DIR / "skill_04_contacted.json"


class Skill04CustomerNotification(BaseSkill):
    """Skill 04: Customer Notification automation.

    Handles abandoned cart detection and recovery email sequences.
    Future: order confirmation, shipping updates, SMS notifications.
    """

    skill_id = "skill_04"
    skill_name = "Customer Notification"

    def __init__(
        self,
        config: AppConfig,
        shopify_client: ShopifyClient,
        ai_client: AIClient,
    ):
        super().__init__(config, shopify_client, ai_client)
        skill_cfg = self._get_skill_config()
        self.check_interval_minutes = getattr(skill_cfg, "abandoned_cart_check_interval_minutes", 15)
        self.sequence = getattr(skill_cfg, "abandoned_cart_sequence", [])
        self.sms_enabled = getattr(skill_cfg, "sms_enabled", False)

        env_map = config.env
        self.email_sender = EmailSender(
            smtp_host=env_map.get("SMTP_HOST", "smtp.klaviyo.com"),
            smtp_port=int(env_map.get("SMTP_PORT", "587")),
            smtp_user=env_map.get("SMTP_USER", ""),
            smtp_password=env_map.get("SMTP_PASSWORD", ""),
            from_email=env_map.get("FROM_EMAIL", config.store_info.contact_email),
            from_name=env_map.get("FROM_NAME", config.store_info.store_name),
        )
        self.cart_detector = AbandonedCartDetector(shopify_client)
        self._jinja = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            autoescape=True,
        )

    def run(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        # Load previously contacted emails to avoid duplicate recovery sends
        contacted = self._load_contacted_log()

        # Fetch abandoned checkouts
        lookback = self.check_interval_minutes * 4  # look back 4x the interval
        abandoned_carts = self.cart_detector.get_abandoned_carts(
            lookback_hours=max(1, lookback // 60),
            exclude_contacted=contacted,
        )

        if not abandoned_carts:
            self.log.info("no_abandoned_carts")
            return result

        for cart in abandoned_carts:
            if result.items_processed >= 50:  # safety limit per run
                result.warnings.append("Hit per-run safety limit of 50 carts")
                break

            result.items_processed += 1
            email = cart["email"]

            try:
                # Determine which sequence step this customer is on
                previous_contacts = self._get_contact_count(email, contacted)
                step_index = min(previous_contacts, len(self.sequence) - 1)

                if step_index < len(self.sequence):
                    step = self.sequence[step_index]
                    self._send_recovery_email(cart, step, dry_run)
                    self._mark_contacted(email, contacted)
                    result.items_succeeded += 1
                    self.log.info("recovery_email_sent", email=email, step=step_index + 1)
                else:
                    self.log.info("sequence_exhausted", email=email)

            except Exception as e:
                result.items_failed += 1
                result.errors.append(SkillErrorDetail(
                    item_id=email,
                    message=str(e),
                    exception_type=type(e).__name__,
                ))

        if dry_run:
            result.metadata["dry_run"] = True
            result.metadata["carts_found"] = len(abandoned_carts)

        return result

    def _send_recovery_email(
        self, cart: dict, step: dict, dry_run: bool = False
    ) -> None:
        """Render and send an abandoned cart recovery email."""
        template_name = step.get("template", "abandoned_cart")
        template_path = f"{template_name}.html"

        discount_code = None
        if step.get("include_discount") and step.get("discount_percentage"):
            discount_code = f"COSMIC{step['discount_percentage']}"

        context = {
            "first_name": cart.get("name", "friend"),
            "line_items": cart.get("line_items", []),
            "cart_url": cart.get("cart_url", "https://mystic-sanctuary.com/cart"),
            "discount_code": discount_code,
            "discount_percentage": step.get("discount_percentage", 0),
            "discount_validity_hours": step.get("discount_validity_hours", 48),
        }

        template = self._jinja.get_template(template_path)
        html_body = template.render(**context)

        self.log.info(
            "email_rendered",
            template=template_path,
            to=cart.get("email"),
            discount=discount_code,
            dry_run=dry_run,
        )

        if not dry_run:
            self.email_sender.send(
                to_email=cart["email"],
                subject="Your cart is waiting — a gentle nudge from the cosmos",
                html_body=html_body,
                to_name=cart.get("name", ""),
            )

    def _load_contacted_log(self) -> dict[str, list[str]]:
        """Load contacted emails map: {email: [contact_timestamps]}."""
        if _CONTACTED_LOG.exists():
            try:
                return json.loads(_CONTACTED_LOG.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {}

    def _save_contacted_log(self, data: dict) -> None:
        _CONTACTED_LOG.parent.mkdir(parents=True, exist_ok=True)
        _CONTACTED_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _get_contact_count(email: str, log: dict) -> int:
        return len(log.get(email, []))

    def _mark_contacted(self, email: str, log: dict) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        log.setdefault(email, []).append(ts)
        self._save_contacted_log(log)
