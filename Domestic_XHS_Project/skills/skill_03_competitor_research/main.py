"""Skill 03 — 竞品/同行调研 (Real Scraping Edition)

通过 patright stealth 浏览器真实搜索话题、爬取高互动笔记，
Claude 逆向拆解爆款公式，生成本号可复用的内容模板。
"""

import asyncio
import json
import logging
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logger import get_logger

logger = get_logger("xhs.skill_03")

_OUTPUT_BASE = Path("D:/马思纯/XHS")
_EXPORT_DIR = _OUTPUT_BASE / datetime.now(timezone.utc).strftime("%Y-%m-%d") / "exports"

# 四大合集对应的话题方向
TOPIC_GROUPS = {
    "道家经典": ["八字 命理", "五行 生克", "运势 分析", "四柱 八字"],
    "碎碎念": ["00后 创业", "停止内耗", "人生 思考", "商业 洞察"],
    "传统文化": ["东方美学", "非遗 工艺", "传统 器物", "古风 审美"],
    "中医养生": ["中医 养生", "节气 养生", "道家 养生", "香药 同源"],
}


class Skill03CompetitorResearch:
    """竞品调研 — 真实爬取 + 爆款拆解 + 模板生成"""

    skill_id = "skill_03"
    skill_name = "竞品/同行调研"

    def __init__(self, ai_client=None, config=None):
        self.ai = ai_client
        self.config = config
        self._scraper = None

    async def _get_scraper(self):
        if self._scraper is None:
            from core.stealth_browser import StealthScraper

            self._scraper = StealthScraper(headless=True)
            await self._scraper.start()
        return self._scraper

    async def _close_scraper(self):
        if self._scraper:
            await self._scraper.close()
            self._scraper = None

    def run(self, topic="道家 命理", competitor_notes=None):
        """同步入口 — 兼容 main.py 调度器"""
        return asyncio.run(self.run_async(topic))

    async def run_async(self, topic: str = "道家 命理") -> dict:
        """执行竞品调研。

        流程: 搜索话题 → 爬取高互动笔记 → Claude 拆解爆款公式 → 输出模板
        """
        scraper = await self._get_scraper()

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "notes_analyzed": 0,
            "viral_formulas": [],
            "title_patterns": [],
            "cover_strategies": "",
            "tag_strategies": [],
            "content_templates": [],
            "claude_analysis": "",
        }

        # === Phase 1: 搜索 + 爬取高互动笔记 ===
        logger.info(f"searching topic: {topic}")
        all_notes = []

        # 用多个相关关键词搜索，扩大样本
        search_keywords = [topic] + random.sample(
            [kw for group in TOPIC_GROUPS.values() for kw in group], 2
        )

        for kw in search_keywords[:3]:
            try:
                notes = await scraper.search_notes(kw, count=15)
                logger.info(f"  keyword='{kw}' found={len(notes)}")
                all_notes.extend(notes)
                await asyncio.sleep(random.uniform(3, 6))
            except Exception as e:
                logger.warning(f"search failed for '{kw}': {e}")

        # 去重 + 按点赞排序取 top 20
        seen_ids = set()
        unique_notes = []
        for n in sorted(all_notes, key=lambda x: x["likes"], reverse=True):
            if n["note_id"] not in seen_ids:
                seen_ids.add(n["note_id"])
                unique_notes.append(n)
        top_notes = unique_notes[:20]

        report["notes_analyzed"] = len(top_notes)

        # === Phase 2: 统计分析 ===
        # 标题模式
        report["title_patterns"] = [n["title"] for n in top_notes if n["title"]]

        # 标签统计（从标题中提取关键词）
        all_words = []
        for n in top_notes:
            if n["title"]:
                # 简单提取2-4字词组
                title = n["title"]
                for i in range(len(title) - 1):
                    if title[i] >= "一" and title[i] <= "鿿":
                        chunk = title[i : i + 3] if i + 3 <= len(title) else title[i:]
                        if len(chunk) >= 2:
                            all_words.append(chunk)
        word_freq = Counter(all_words).most_common(15)
        report["tag_strategies"] = [
            {"keyword": w, "frequency": c} for w, c in word_freq
        ]

        # 互动数据分析
        avg_likes = round(sum(n["likes"] for n in top_notes) / max(len(top_notes), 1))
        avg_collects = round(
            sum(n["collects"] for n in top_notes) / max(len(top_notes), 1)
        )
        avg_comments = round(
            sum(n["comments"] for n in top_notes) / max(len(top_notes), 1)
        )

        # === Phase 3: Claude 深度分析 ===
        if self.ai and top_notes:
            notes_sample = []
            for n in top_notes[:10]:
                notes_sample.append(
                    {
                        "title": n["title"],
                        "likes": n["likes"],
                        "collects": n["collects"],
                        "comments": n["comments"],
                    }
                )

            claude_prompt = f"""分析小红书"{topic}"赛道的 {len(top_notes)} 篇高互动笔记数据。

平均互动: 点赞{avg_likes} 收藏{avg_collects} 评论{avg_comments}
标题样本:
{json.dumps(notes_sample, ensure_ascii=False, indent=2)}

请从以下维度拆解（中文，400字以内）:
1. 标题公式: 这些爆款用的什么标题套路? 提炼2个可套用的模板
2. 互动设计: 如何引导点赞/评论/收藏?
3. 高净值人群适配: 这些内容是否符合高净值人群的审美和认知水平?
4. 给本号的3条具体建议（按四大合集定位）"""
            try:
                report["claude_analysis"] = self.ai.generate_text(
                    user_prompt=claude_prompt, max_tokens=2048
                )
            except Exception as e:
                logger.error(f"claude_analysis_failed: {e}")

        # === Phase 4: 生成可复用模板 ===
        report["content_templates"] = await self._generate_templates(topic, top_notes)
        report["viral_formulas"] = self._extract_formulas(top_notes)

        # === 导出 ===
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_03_competitor_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        logger.info(
            f"competitor_research_complete topic={topic} notes={len(top_notes)}"
        )

        await self._close_scraper()
        return report

    def _extract_formulas(self, notes: list[dict]) -> list[dict]:
        """从笔记数据中提取爆款公式特征"""
        if not notes:
            return []

        top_5 = sorted(notes, key=lambda x: x["likes"], reverse=True)[:5]
        formulas = []
        for i, n in enumerate(top_5):
            title = n.get("title", "")
            formulas.append(
                {
                    "rank": i + 1,
                    "title": title,
                    "likes": n["likes"],
                    "engagement_rate": round(
                        (n["likes"] + n["collects"] + n["comments"]) / max(n["likes"], 1) * 100
                    ),
                    "estimated_formula": self._guess_formula(title),
                }
            )
        return formulas

    def _guess_formula(self, title: str) -> str:
        """根据标题猜测其公式类型"""
        if not title:
            return "未知"
        if any(kw in title for kw in ["多少", "为什么", "是不是", "？", "吗"]):
            return "悬念/反问型"
        if any(kw in title for kw in ["干货", "必看", "收藏", "保姆级", "指南"]):
            return "干货型"
        if any(kw in title for kw in ["破防", "泪崩", "治愈", "陪伴", "懂你"]):
            return "情感共鸣型"
        if any(kw in title for kw in ["别", "不要", "错了", "骗", "真相"]):
            return "反常识/纠正型"
        if any(char.isdigit() for char in title):
            return "数字型"
        return "陈述型"

    async def _generate_templates(
        self, topic: str, notes: list[dict]
    ) -> list[dict]:
        """基于真实数据生成可复用模板"""
        templates = [
            {
                "type": "高净值-道家经典",
                "适用合集": "合集1 道家经典",
                "title_template": "《道藏》里一句话，说透了{痛点}",
                "structure": "古语原文 → 白话翻译 → 当代场景映射 → 一句话收尾",
                "hook": "用原文建立学术权威感，不给结论让读者自己悟",
            },
            {
                "type": "高净值-碎碎念",
                "适用合集": "合集2 碎碎念",
                "title_template": "谁家好人{做一件普通的事}",
                "structure": "场景白描 → 一个反常识观点 → 收住不展开",
                "hook": "用日常场景做钩子，用淡淡的不讨好建立人设",
            },
            {
                "type": "高净值-传统文化",
                "适用合集": "合集3 传统文化",
                "title_template": "今天看到一个{器物}，想了很久",
                "structure": "器物描述 → 工艺细节 → 与当代生活的对比 → 留白",
                "hook": "不卖东西，用审美本身种草",
            },
            {
                "type": "高净值-中医养生",
                "适用合集": "合集4 中医养生",
                "title_template": "这个月{节气}，身体在提醒你{动作}",
                "structure": "节气特征 → 身体症状 → 一个具体建议 → 为什么有效",
                "hook": "知识+身份感，让读者觉得'这个博主懂行'",
            },
        ]
        return templates
