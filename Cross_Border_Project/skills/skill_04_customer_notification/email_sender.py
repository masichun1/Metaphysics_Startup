"""Email sending via SMTP for customer notifications."""

import logging
from core.logger import get_logger
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = get_logger("metaphysics.skill_04")


class EmailSender:
    """Send transactional emails via SMTP (compatible with Klaviyo, Mailchimp, SendGrid)."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        from_email: str = "support@mysticsanctuary.com",
        from_name: str = "Mystic Sanctuary",
    ):
        self.host = smtp_host
        self.port = smtp_port
        self.user = smtp_user
        self.password = smtp_password
        self.from_email = from_email
        self.from_name = from_name

    def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        to_name: str = "",
        plain_text: str = "",
    ) -> bool:
        """Send a single email. Returns True on success."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            recipient = f"{to_name} <{to_email}>" if to_name else to_email
            msg["To"] = recipient
            msg["Subject"] = subject

            if plain_text:
                msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, to_email, msg.as_string())

            logger.info("email_sent", to=to_email, subject=subject)
            return True
        except Exception as e:
            logger.error("email_failed", to=to_email, subject=subject, error=str(e))
            return False

    def send_batch(
        self,
        recipients: list[dict[str, str]],
        subject_template: str,
        body_template: str,
    ) -> tuple[int, int]:
        """Send batch emails. Returns (sent_count, failed_count)."""
        sent, failed = 0, 0
        for r in recipients:
            subject = subject_template.format(**r)
            body = body_template.format(**r)
            success = self.send(
                to_email=r.get("email", ""),
                subject=subject,
                html_body=body,
                to_name=r.get("name", ""),
            )
            if success:
                sent += 1
            else:
                failed += 1
        return sent, failed
