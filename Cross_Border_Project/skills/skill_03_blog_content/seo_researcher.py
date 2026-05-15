"""SEO keyword research helper for blog content generation."""

import logging
from core.logger import get_logger
import random
from datetime import datetime, timezone

logger = get_logger("metaphysics.skill_03")


class SEOResearcher:
    """Lightweight keyword research tool.

    In production, this would integrate with SEMrush API, Google Keyword Planner,
    or Ahrefs for real search volume and competition data. Currently provides
    topic selection logic and keyword expansion.
    """

    # Secondary keyword expansion map for common metaphysical topics
    KEYWORD_EXPANSIONS: dict[str, list[str]] = {
        "astrology": [
            "astrology basics", "astrology chart reading", "birth chart",
            "astrology signs", "astrology for beginners", "planetary transits",
        ],
        "crystal": [
            "crystal healing properties", "crystal meanings", "healing stones",
            "crystal grid", "crystal bracelet", "raw crystals",
        ],
        "tarot": [
            "tarot card meanings", "tarot spreads", "tarot reading online",
            "tarot deck review", "daily tarot", "intuitive tarot",
        ],
        "feng shui": [
            "feng shui basics", "feng shui home", "feng shui colors",
            "feng shui office", "feng shui plants", "feng shui wealth corner",
        ],
        "meditation": [
            "guided meditation", "mindfulness meditation", "meditation for sleep",
            "morning meditation", "meditation techniques", "meditation benefits",
        ],
    }

    @classmethod
    def expand_keywords(cls, topic: str, category: str, seed_keywords: list[str]) -> list[str]:
        """Expand a seed keyword list with relevant secondary keywords."""
        expanded = list(seed_keywords)
        category_lower = category.lower()

        for key, expansions in cls.KEYWORD_EXPANSIONS.items():
            if key in category_lower or key in topic.lower():
                # Add 2-3 random expansions not already in the list
                candidates = [k for k in expansions if k not in expanded]
                selected = random.sample(candidates, min(3, len(candidates)))
                expanded.extend(selected)
                break

        return expanded

    @classmethod
    def pick_next_topic(cls, topics: list[dict], published_history: list[str]) -> dict | None:
        """Pick the next topic to publish, avoiding recently used topics."""
        available = [
            t for t in topics
            if t["topic"] not in published_history
        ]
        if not available:
            # Reset history when all topics have been used
            available = topics
            logger.info("topic_cycle_reset", total_topics=len(topics))

        if not available:
            return None

        # Pick based on month — alternate categories for variety
        current_month = datetime.now(timezone.utc).month
        idx = current_month % len(available)
        return available[idx]
