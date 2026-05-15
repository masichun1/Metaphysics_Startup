"""Skill 02 — 评论区监控 (Comment Monitor)

实时分析评论区情绪，提取高频问题或潜在客户意向线索。
OpenCLI 爬取评论区 -> Claude NLP 情感分析 + 意图识别 -> 输出潜在客户名单和应对话术。
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("xhs.skill_02")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill02CommentMonitor:
    """评论区监控 — 情感分析 + 潜在线索提取"""

    skill_id = "skill_02"
    skill_name = "评论区监控"

    # 购买意向关键词（中文）
    PURCHASE_INTENT_KEYWORDS = [
        "多少钱", "怎么买", "在哪里买", "价格", "链接",
        "私我", "求推荐", "想买", "哪里可以", "怎么预约",
        "收费", "课程", "服务", "咨询",
    ]

    # 高价值问题关键词
    HIGH_VALUE_QUESTION_KEYWORDS = [
        "怎么样", "有用吗", "真的假的", "效果", "准吗",
        "怎么用", "适合吗", "会不会", "能不能",
    ]

    def __init__(self, ai_client=None, browser_manager=None, config=None):
        self.ai = ai_client
        self.browser = browser_manager
        self.config = config

    def run(
        self,
        comments: list[dict] | None = None,
        note_title: str = "",
    ) -> dict:
        """分析评论区数据。

        Args:
            comments: 评论列表，每条包含 {content, likes, user_name, time}。
            note_title: 被分析笔记的标题。

        Returns:
            分析报告 dict。
        """
        comments = comments or []
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note_title": note_title,
            "total_comments": len(comments),
            "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
            "high_frequency_keywords": [],
            "purchase_intent_leads": [],
            "high_value_questions": [],
            "claude_analysis": "",
        }

        # Rule-based sentiment + keyword extraction (lightweight, no AI needed for basics)
        all_words = []
        for c in comments:
            content = c.get("content", "")
            user = c.get("user_name", "")

            # Simple sentiment
            sentiment = self._classify_sentiment(content)
            report["sentiment_distribution"][sentiment] += 1

            # Collect words for frequency analysis
            words = self._tokenize(content)
            all_words.extend(words)

            # Detect purchase intent
            if self._has_purchase_intent(content):
                report["purchase_intent_leads"].append({
                    "user_name": user,
                    "comment": content,
                    "time": c.get("time", ""),
                    "intent_score": self._calculate_intent_score(content),
                })

            # Detect high-value questions
            if self._is_high_value_question(content):
                report["high_value_questions"].append({
                    "user_name": user,
                    "question": content,
                    "time": c.get("time", ""),
                })

        # Word frequency
        word_counts = Counter(all_words)
        report["high_frequency_keywords"] = word_counts.most_common(30)

        # Claude deep analysis
        if self.ai and comments:
            sample = "\n".join([c.get("content", "") for c in comments[:50]])
            claude_prompt = f"""分析以下小红书评论区的数据：

笔记标题：{note_title}
评论总数：{len(comments)}
评论抽样（前50条）：
{sample}

请从以下维度给出分析（中文，500字以内）：
1. 评论整体情绪基调（正面/负面占比和原因）
2. 用户最关心的3个核心问题
3. 内容改进建议（基于用户反馈）
4. 是否有可转化的商业线索？如何跟进？"""
            try:
                report["claude_analysis"] = self.ai.generate_text(
                    user_prompt=claude_prompt
                )
            except Exception as e:
                logger.error("claude_analysis_failed", error=str(e))
                report["claude_analysis"] = "AI 分析暂不可用"

        # Export
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_02_comments_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(
            "comment_analysis_complete",
            total=len(comments),
            leads=len(report["purchase_intent_leads"]),
        )

        return report

    @classmethod
    def _classify_sentiment(cls, text: str) -> str:
        """Simple rule-based Chinese sentiment classification."""
        positive_words = ["好", "赞", "喜欢", "厉害", "准", "有用", "感谢", "谢谢", "推荐", "棒", "绝", "太", "真的"]
        negative_words = ["差", "骗", "坑", "假", "不准", "没用", "失望", "垃圾", "后悔", "烂"]

        pos_score = sum(1 for w in positive_words if w in text)
        neg_score = sum(1 for w in negative_words if w in text)

        if pos_score > neg_score:
            return "positive"
        elif neg_score > pos_score:
            return "negative"
        return "neutral"

    @classmethod
    def _has_purchase_intent(cls, text: str) -> bool:
        return any(kw in text for kw in cls.PURCHASE_INTENT_KEYWORDS)

    @classmethod
    def _is_high_value_question(cls, text: str) -> bool:
        return any(kw in text for kw in cls.HIGH_VALUE_QUESTION_KEYWORDS)

    @classmethod
    def _calculate_intent_score(cls, text: str) -> float:
        """0-1 score based on how many intent keywords match."""
        matches = sum(1 for kw in cls.PURCHASE_INTENT_KEYWORDS if kw in text)
        return min(1.0, matches / 3.0)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple Chinese text tokenization (jieba would be better)."""
        # Remove punctuation and split into 2-4 char chunks
        cleaned = re.sub(r'[^一-鿿\w]', '', text)
        tokens = []
        for size in [2, 3, 4]:
            for i in range(len(cleaned) - size + 1):
                tokens.append(cleaned[i:i + size])
        return tokens
