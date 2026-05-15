"""Skill 03 — WordPress 博客内容撰写 (Blog Content)

AI 生成 SEO 英文博客文章 → WordPress REST API 自动发布
"""
import json, logging, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ai_client import AIClient
from core.config_loader import AppConfig
from core.logger import get_logger
from core.woocommerce_client import WordPressClient
from skills.skill_base import BaseSkill, SkillErrorDetail, SkillResult
from skills.skill_03_blog_content.content_calendar import TOPIC_CALENDAR
from skills.skill_03_blog_content.seo_researcher import SEOResearcher

logger = get_logger("metaphysics.wp_skill_03")
_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"
_PUBLISHED_LOG = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "wp_skill_03_published.json"


class Skill03WPBlog(BaseSkill):
    skill_id = "wp_skill_03"
    skill_name = "WordPress Blog Content"

    def __init__(self, config: AppConfig, wp: WordPressClient, ai: AIClient):
        super().__init__(config, wp, ai)
        self.wp = wp

    def run(self, dry_run: bool = False, **kwargs) -> SkillResult:
        result = SkillResult(skill_id=self.skill_id, run_id=self.generate_run_id())

        topic_override = kwargs.get("topic")
        if topic_override:
            selected = {"topic": topic_override, "category": kwargs.get("category", "Spirituality"),
                        "keywords": kwargs.get("keywords", []), "target_word_count": kwargs.get("target_word_count", 2000)}
        else:
            published = self._load_published()
            selected = SEOResearcher.pick_next_topic(TOPIC_CALENDAR, published)
            if not selected:
                result.errors.append(SkillErrorDetail(message="No available topics"))
                return result

        keywords = SEOResearcher.expand_keywords(selected["topic"], selected["category"], selected.get("keywords", []))
        result.items_processed = 1

        try:
            article = self.ai.generate_blog_article(
                topic=selected["topic"], category=selected["category"],
                keywords=keywords, target_word_count=selected.get("target_word_count", 2000),
            )
        except Exception as e:
            result.items_failed = 1
            result.errors.append(SkillErrorDetail(message=str(e)))
            return result

        if dry_run:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            export_path = _EXPORT_DIR / f"wp_skill_03_{ts}.json"
            _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(article, indent=2), encoding="utf-8")
            result.items_succeeded = 1
            return result

        # Publish to WordPress
        try:
            post_data = {
                "title": article.get("title", selected["topic"]),
                "content": article.get("body_html", ""),
                "excerpt": article.get("excerpt", ""),
                "status": "publish",
                "categories": [selected["category"]],
                "tags": article.get("tags", []),
            }
            created = self.wp.create_post(post_data)
            self._append_published(selected["topic"])
            result.items_succeeded = 1
            result.metadata["post_id"] = created.get("id")
            self.log.info("published", post_id=created.get("id"), topic=selected["topic"])
        except Exception as e:
            result.items_failed = 1
            result.errors.append(SkillErrorDetail(message=str(e)))

        return result

    def _load_published(self) -> list[str]:
        if _PUBLISHED_LOG.exists():
            try:
                return json.loads(_PUBLISHED_LOG.read_text(encoding="utf-8")).get("topics", [])
            except Exception:
                pass
        return []

    def _append_published(self, topic: str) -> None:
        _PUBLISHED_LOG.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _PUBLISHED_LOG.exists():
            try:
                data = json.loads(_PUBLISHED_LOG.read_text(encoding="utf-8"))
            except Exception:
                pass
        data.setdefault("topics", []).append(topic)
        _PUBLISHED_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")
