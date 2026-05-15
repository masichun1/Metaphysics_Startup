import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.ai_client import AIClient
from core.config_loader import AppConfig, SkillsConfig
from core.logger import get_logger
from core.shopify_client import ShopifyClient


@dataclass
class SkillErrorDetail:
    item_id: str = ""
    message: str = ""
    exception_type: str = ""


@dataclass
class SkillResult:
    skill_id: str
    run_id: str
    status: str = "success"  # "success", "partial_success", "failed"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    items_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    errors: list[SkillErrorDetail] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0


class BaseSkill(ABC):
    """
    Abstract base class for all automation skills.

    Lifecycle: validate_config() -> run() -> SkillResult
    """

    skill_id: str = "base"
    skill_name: str = "Base Skill"

    def __init__(
        self,
        config: AppConfig,
        shopify_client: ShopifyClient,
        ai_client: AIClient,
    ):
        self.config = config
        self.shopify = shopify_client
        self.ai = ai_client
        self.log = get_logger().bind(skill_id=self.skill_id)

    @abstractmethod
    def run(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        """Execute the skill. dry_run=True means no API writes."""
        ...

    def validate_config(self) -> list[str]:
        """Return list of config issues. Empty list means valid."""
        issues = []
        skill_config = self._get_skill_config()
        if skill_config is None:
            issues.append(f"No config found for {self.skill_id}")
        elif not skill_config.enabled:
            issues.append(f"Skill {self.skill_id} is disabled in config")
        return issues

    def _get_skill_config(self) -> Any | None:
        """Get the skill-specific config section."""
        skills = self.config.skills
        mapping = {
            "skill_01": skills.skill_01_product_listing,
            "skill_02": skills.skill_02_product_reviews,
            "skill_03": skills.skill_03_blog_content,
            "skill_04": skills.skill_04_customer_notification,
            "skill_05": skills.skill_05_revenue_calculation,
        }
        return mapping.get(self.skill_id)

    def generate_run_id(self) -> str:
        return f"{self.skill_id}-{uuid.uuid4().hex[:12]}"

    def execute(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        """Template method that wraps run() with validation and logging."""
        issues = self.validate_config()
        if issues:
            for issue in issues:
                self.log.warning("config_issue", issue=issue)

        run_id = self.generate_run_id()
        self.log = self.log.bind(run_id=run_id)
        self.log.info("skill_start", skill_name=self.skill_name, dry_run=dry_run)

        try:
            result = self.run(dry_run=dry_run, **kwargs)
            result.skill_id = self.skill_id
            result.run_id = run_id
            result.finish()

            if result.items_failed > 0 and result.items_succeeded > 0:
                result.status = "partial_success"
            elif result.items_succeeded == 0 and result.items_processed > 0:
                result.status = "failed"

            self.log.info(
                "skill_end",
                status=result.status,
                processed=result.items_processed,
                succeeded=result.items_succeeded,
                failed=result.items_failed,
                duration_s=round(result.duration_seconds, 2),
            )
            return result
        except Exception as e:
            self.log.error("skill_error", error=str(e), exc_info=True)
            result = SkillResult(
                skill_id=self.skill_id,
                run_id=run_id,
                status="failed",
            )
            result.errors.append(SkillErrorDetail(
                message=str(e),
                exception_type=type(e).__name__,
            ))
            result.finish()
            return result
