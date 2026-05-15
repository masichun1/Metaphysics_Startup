"""Skill 03: Blog Content — generate and publish SEO-optimized English blog articles."""

import json
import logging
from core.logger import get_logger
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.shopify_client import ShopifyClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_03_blog_content.content_calendar import TOPIC_CALENDAR
from skills.skill_03_blog_content.seo_researcher import SEOResearcher

logger = get_logger("metaphysics.skill_03")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"
_PUBLISHED_LOG = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "skill_03_published.json"


class Skill03BlogContent(BaseSkill):
    """Skill 03: Blog Content automation.

    Flow: pick topic -> expand keywords -> AI generate article -> publish to Shopify Blog.
    """

    skill_id = "skill_03"
    skill_name = "Blog Content"

    def __init__(
        self,
        config: AppConfig,
        shopify_client: ShopifyClient,
        ai_client: AIClient,
    ):
        super().__init__(config, shopify_client, ai_client)
        skill_cfg = self._get_skill_config()
        self.default_blog_handle = getattr(skill_cfg, "default_blog_handle", "news")
        self.article_length_min = getattr(skill_cfg, "article_length_min", 1500)
        self.article_length_max = getattr(skill_cfg, "article_length_max", 3000)
        self.auto_publish = getattr(skill_cfg, "auto_publish", True)

    def run(self, dry_run: bool = False, **kwargs: Any) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        # Determine topic
        topic_override = kwargs.get("topic")
        if topic_override:
            selected_topic = {
                "topic": topic_override,
                "category": kwargs.get("category", "Spirituality"),
                "keywords": kwargs.get("keywords", []),
                "target_word_count": kwargs.get("target_word_count", 2000),
            }
        else:
            published_history = self._load_published_log()
            selected_topic = SEOResearcher.pick_next_topic(TOPIC_CALENDAR, published_history)
            if selected_topic is None:
                result.errors.append(SkillErrorDetail(message="No available topics to publish"))
                result.status = "failed"
                return result

        topic_name = selected_topic["topic"]
        category = selected_topic["category"]
        keywords = SEOResearcher.expand_keywords(
            topic_name, category, selected_topic.get("keywords", [])
        )
        target_wc = selected_topic.get("target_word_count", 2000)

        result.items_processed = 1
        self.log.info("generating_article", topic=topic_name, category=category)

        try:
            article = self.ai.generate_blog_article(
                topic=topic_name,
                category=category,
                keywords=keywords,
                target_word_count=target_wc,
            )
        except Exception as e:
            result.items_failed = 1
            result.errors.append(SkillErrorDetail(
                item_id=topic_name,
                message=str(e),
                exception_type=type(e).__name__,
            ))
            result.status = "failed"
            return result

        if dry_run:
            # Export to JSON for review
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            export_path = _EXPORT_DIR / f"skill_03_article_{ts}.json"
            export_path.write_text(
                json.dumps({
                    "topic": topic_name,
                    "category": category,
                    "keywords": keywords,
                    "article": article,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            result.metadata["export_path"] = str(export_path)
            result.metadata["dry_run"] = True
            result.items_succeeded = 1
            self.log.info("dry_run_article", path=str(export_path))
            return result

        # Publish to Shopify Blog
        try:
            blog = self.shopify.get_blog_by_handle(self.default_blog_handle)
            if blog is None:
                result.errors.append(SkillErrorDetail(
                    message=f"Blog with handle '{self.default_blog_handle}' not found"
                ))
                result.status = "failed"
                return result

            blog_id = blog["id"]
            article_payload = {
                "title": article.get("title", topic_name),
                "body_html": article.get("body_html", ""),
                "summary_html": article.get("excerpt", ""),
                "author": self.config.store_info.store_name,
                "tags": ", ".join(article.get("tags", [])),
                "published": self.auto_publish,
            }

            if not self.auto_publish:
                article_payload["published_at"] = None  # draft

            created = self.shopify.create_article(blog_id, article_payload)
            article_id = created.get("id", "unknown")
            self.log.info("article_published", article_id=article_id, topic=topic_name)

            # Track published topic
            self._append_published_log(topic_name)

            result.items_succeeded = 1
            result.metadata["article_id"] = article_id
            result.metadata["blog_handle"] = self.default_blog_handle

        except Exception as e:
            result.items_failed = 1
            result.errors.append(SkillErrorDetail(
                item_id=topic_name,
                message=str(e),
                exception_type=type(e).__name__,
            ))
            self.log.error("publish_failed", topic=topic_name, error=str(e))

        return result

    def _load_published_log(self) -> list[str]:
        """Load list of recently published article titles."""
        if _PUBLISHED_LOG.exists():
            try:
                data = json.loads(_PUBLISHED_LOG.read_text(encoding="utf-8"))
                return data.get("published_topics", [])
            except (json.JSONDecodeError, KeyError):
                return []
        return []

    def _append_published_log(self, topic: str) -> None:
        """Record a published topic in the history log."""
        _PUBLISHED_LOG.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _PUBLISHED_LOG.exists():
            try:
                data = json.loads(_PUBLISHED_LOG.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        topics = data.get("published_topics", [])
        topics.append(topic)
        data["published_topics"] = topics
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        _PUBLISHED_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")
