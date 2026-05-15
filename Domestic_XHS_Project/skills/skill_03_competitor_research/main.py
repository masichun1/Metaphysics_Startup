"""Skill 03 — 竞品/同行调研 (Competitor Research)

爬取并拆解爆款图文的结构、文案逻辑和标签。
OpenCLI 爬取 -> Claude 逆向拆解爆款公式 -> 生成本号可复用的内容模板。
"""

import json
import logging
from core.logger import get_logger
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = get_logger("xhs.skill_03")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill03CompetitorResearch:
    """竞品调研 — 爆款笔记拆解 + 内容公式提取"""

    skill_id = "skill_03"
    skill_name = "竞品/同行调研"

    # 玄学赛道热门话题
    HOT_TOPICS = [
        "塔罗占卜", "星座运势", "八字分析", "风水布局",
        "水晶", "能量疗愈", "紫微斗数", "面相手相",
        "生肖运程", "冥想修行", "脉轮", "吸引力法则",
    ]

    def __init__(self, ai_client=None, browser_manager=None, config=None):
        self.ai = ai_client
        self.browser = browser_manager
        self.config = config

    def run(
        self,
        topic: str = "塔罗",
        competitor_notes: list[dict] | None = None,
    ) -> dict:
        """执行竞品调研。

        Args:
            topic: 调研的话题/赛道。
            competitor_notes: OpenCLI 爬取的爆款笔记数据列表。
                Each dict: {title, content, likes, comments, collects, tags, cover_style, publish_time}

        Returns:
            结构化调研报告 dict。
        """
        competitor_notes = competitor_notes or []

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "notes_analyzed": len(competitor_notes),
            "viral_formulas": [],  # 爆款公式
            "title_patterns": [],  # 标题模式
            "cover_styles": {},  # 封面风格分布
            "tag_strategies": [],  # 标签策略
            "content_templates": [],  # 可复用内容模板
            "claude_analysis": "",
        }

        # Statistical analysis
        title_patterns = []
        all_tags = []
        cover_counts: dict[str, int] = {}

        for note in competitor_notes:
            title = note.get("title", "")
            tags = note.get("tags", [])
            cover = note.get("cover_style", "未知")

            title_patterns.append(title)
            all_tags.extend(tags)
            cover_counts[cover] = cover_counts.get(cover, 0) + 1

            # Estimate engagement rate
            likes = note.get("likes", 0)
            comments = note.get("comments", 0)
            collects = note.get("collects", 0)

        report["title_patterns"] = title_patterns[:20]
        report["cover_styles"] = dict(
            sorted(cover_counts.items(), key=lambda x: x[1], reverse=True)
        )
        report["tag_strategies"] = [
            {"tag": tag, "frequency": freq}
            for tag, freq in Counter(all_tags).most_common(20)
        ]

        # Claude deep analysis
        if self.ai and competitor_notes:
            notes_sample = json.dumps(
                [
                    {
                        "title": n.get("title", ""),
                        "likes": n.get("likes", 0),
                        "tags": n.get("tags", []),
                    }
                    for n in competitor_notes[:10]
                ],
                ensure_ascii=False,
                indent=2,
            )

            claude_prompt = f"""分析小红书"玄学-{topic}"赛道的以下爆款笔记数据，逆向拆解它们的成功公式。

爆款笔记样本（前10条）：
{notes_sample}

请从以下维度拆解（中文，800字以内）：
1. 标题公式：这些爆款用了什么标题套路？（悬念型、数字型、情感型、反常识型？）提炼2-3个可直接套用的标题模板。
2. 文案结构：正文是如何组织的？开头怎么抓人？每个部分的目的是什么？
3. 互动设计：它们如何引导用户点赞、评论、收藏？
4. 封面策略：观察到的封面类型分布，哪种最有效？
5. 标签组合：高互动笔记的标签使用规律。
6. 给本号的3条具体执行建议。"""
            try:
                report["claude_analysis"] = self.ai.generate_text(
                    user_prompt=claude_prompt,
                    max_tokens=2048,
                )
            except Exception as e:
                logger.error("claude_analysis_failed", error=str(e))

        # Generate reusable templates
        if self.ai:
            report["content_templates"] = self._generate_templates(topic)

        # Export
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_03_competitor_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("competitor_research_complete", topic=topic, notes=len(competitor_notes))

        return report

    def _generate_templates(self, topic: str) -> list[dict]:
        """Generate reusable content templates based on analysis."""
        templates = [
            {
                "type": "悬念型",
                "title_template": f"{{number}}个{topic}的秘密，第{{N}}个让人意想不到",
                "structure": "开头悬念 -> 逐个揭秘 -> 互动引导",
                "example": f"5个塔罗牌的秘密，第3个让我起鸡皮疙瘩",
            },
            {
                "type": "干货型",
                "title_template": f"{topic}新手必看！{topic}入门指南（建议收藏）",
                "structure": "痛点引入 -> 分步教程 -> 收藏引导",
                "example": "塔罗新手必看！3分钟学会最简单的三牌阵",
            },
            {
                "type": "情感型",
                "title_template": f"如果你正在经历{{情感}}，{topic}想对你说...",
                "structure": "情感共鸣 -> {topic}解读 -> 温暖收尾",
                "example": "如果你正在经历分手，塔罗想对你说这些话",
            },
            {
                "type": "争议型",
                "title_template": f"为什么你的{{行为}}可能是错的？{topic}告诉你真相",
                "structure": "观点抛出 -> 论据支撑 -> 评论区讨论引导",
                "example": "为什么你的冥想可能是错的？90%的人都忽略了这个",
            },
        ]
        return templates
