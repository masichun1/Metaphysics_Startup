"""Skill 01 — 数据自动追踪 (Real Scraping Edition)

通过 patright stealth 浏览器真实搜索关键词，抓取笔记数据，
将生数据传给 Claude 分析趋势，输出可执行优化建议。

不再使用 AI 凭空生成数据。
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logger import get_logger

logger = get_logger("xhs.skill_01")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"
_CSV_DIR = _EXPORT_DIR.parent / "csv"

# 默认追踪关键词 — 基于玄学赛道四大合集
DEFAULT_KEYWORDS = [
    # 合集1: 道家经典 + 命理
    "八字 命理 运势",
    "道家 智慧 人生",
    "五行 相生相克",
    # 合集2: 修心 + 商业洞察
    "00后 创业 思考",
    "停止 内耗 道家",
    # 合集3: 传统文化
    "东方美学 器物",
    "非遗 手工艺",
    # 合集4: 中医养生
    "中医 养生 日常",
    "节气 养生 道家",
]

BENCHMARK_ACCOUNTS = [
    "玄学大师姐",
    "塔罗师小K",
]


class Skill01DataTracking:
    """数据自动追踪 — 真实爬取 + Claude 分析"""

    skill_id = "skill_01"
    skill_name = "数据自动追踪"

    def __init__(self, ai_client=None, config=None):
        self.ai = ai_client
        self.config = config
        self._scraper = None

    async def _get_scraper(self):
        """懒加载浏览器爬取器"""
        if self._scraper is None:
            from core.stealth_browser import StealthScraper

            self._scraper = StealthScraper(headless=True)
            await self._scraper.start()
        return self._scraper

    async def _close_scraper(self):
        if self._scraper:
            await self._scraper.close()
            self._scraper = None

    def run(self, keywords=None, accounts=None, note_count=20):
        """同步入口 — 兼容 main.py 调度器"""
        return asyncio.run(self.run_async(keywords, accounts, note_count))

    async def run_async(
        self,
        keywords: list[str] | None = None,
        accounts: list[str] | None = None,
        note_count: int = 20,
    ) -> dict:
        """执行真实数据追踪。

        流程: 浏览器搜索 → 抓取数据 → Claude 分析 → 导出报告
        """
        keywords = keywords or DEFAULT_KEYWORDS
        accounts = accounts or BENCHMARK_ACCOUNTS

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "keywords_analysis": [],
            "account_analysis": [],
            "market_trends": "",
            "alerts": [],
        }

        scraper = await self._get_scraper()

        # === Phase 1: 关键词搜索 + 数据抓取 ===
        all_search_results = []
        for kw in keywords:
            logger.info(f"searching keyword: {kw}")
            try:
                notes = await scraper.search_notes(kw, count=note_count)
                # 加随机延迟避免风控
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.warning(f"search failed for '{kw}': {e}")
                notes = []

            analysis = {
                "keyword": kw,
                "notes_collected": len(notes),
                "avg_likes": round(sum(n["likes"] for n in notes) / max(len(notes), 1)),
                "avg_comments": round(
                    sum(n["comments"] for n in notes) / max(len(notes), 1)
                ),
                "avg_collects": round(
                    sum(n["collects"] for n in notes) / max(len(notes), 1)
                ),
                "top_notes": sorted(notes, key=lambda x: x["likes"], reverse=True)[:5],
                "claude_insight": "",
            }

            # Claude 分析当前关键词的数据
            if self.ai and notes:
                titles_sample = [n["title"] for n in notes[:10] if n["title"]]
                insight_prompt = f"""分析小红书关键词"{kw}"的搜索结果数据：

实际抓取到 {len(notes)} 篇笔记。
前10篇标题: {json.dumps(titles_sample, ensure_ascii=False)}
平均点赞: {analysis['avg_likes']}  平均收藏: {analysis['avg_collects']}  平均评论: {analysis['avg_comments']}

请给出:
1. 当前话题内容特征（标题风格、内容类型）
2. 爆款潜力判断（3句话）
3. 本号切入建议（2条可执行动作）

用中文，150字以内。"""
                try:
                    insight = self.ai.generate_text(user_prompt=insight_prompt)
                    analysis["claude_insight"] = insight
                except Exception as e:
                    logger.warning(f"Claude insight failed: {e}")

            report["keywords_analysis"].append(analysis)
            all_search_results.extend(notes)

        # === Phase 2: 对标账号爬取 ===
        for account_name in accounts:
            logger.info(f"searching account: {account_name}")
            try:
                users = await scraper.search_users(account_name, count=3)
                await asyncio.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.warning(f"user search failed: {e}")
                users = []

            account_data = {
                "account": account_name,
                "found": len(users) > 0,
                "user_info": users[0] if users else {},
                "recent_notes": [],
                "claude_insight": "",
            }

            # 如果找到了用户，爬取其笔记
            if users and users[0].get("user_id"):
                uid = users[0]["user_id"]
                try:
                    notes = await scraper.get_user_notes(uid, count=15)
                    account_data["recent_notes"] = notes
                    await asyncio.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.warning(f"get_user_notes failed: {e}")

            # Claude 分析
            if self.ai and account_data["recent_notes"]:
                notes_data = account_data["recent_notes"][:10]
                note_summary = [
                    {
                        "title": n["title"],
                        "likes": n["likes"],
                        "collects": n["collects"],
                    }
                    for n in notes_data
                ]
                insight_prompt = f"""分析小红书账号"{account_name}"的运营数据：

实际抓取到 {len(notes_data)} 篇笔记:
{json.dumps(note_summary, ensure_ascii=False)}

请给出:
1. 账号内容策略特征
2. 为什么最近几篇数据好/差
3. 本号可复用的1个技巧

用中文，150字以内。"""
                try:
                    insight = self.ai.generate_text(user_prompt=insight_prompt)
                    account_data["claude_insight"] = insight
                except Exception as e:
                    logger.warning(f"Claude insight failed: {e}")

            report["account_analysis"].append(account_data)

        # === Phase 3: 全局趋势分析 ===
        if self.ai and all_search_results:
            all_titles = [n["title"] for n in all_search_results if n["title"]]
            trend_prompt = f"""基于小红书玄学赛道 {len(all_search_results)} 篇笔记的标题数据，
分析当前市场趋势:

标题样本: {json.dumps(all_titles[:20], ensure_ascii=False)}

请总结:
1. 当前赛道主流内容方向（2-3个）
2. 爆款标题公式（1-2个）
3. 本号本周最该发的一个选题

用中文，200字以内。"""
            try:
                report["market_trends"] = self.ai.generate_text(
                    user_prompt=trend_prompt
                )
            except Exception:
                report["market_trends"] = ""

        # === 导出 ===
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_01_data_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # CSV 导出
        _CSV_DIR.mkdir(parents=True, exist_ok=True)
        csv_lines = ["keyword,notes,avg_likes,avg_comments,avg_collects"]
        for ka in report["keywords_analysis"]:
            csv_lines.append(
                f'{ka["keyword"]},{ka["notes_collected"]},{ka["avg_likes"]},{ka["avg_comments"]},{ka["avg_collects"]}'
            )
        csv_path = _CSV_DIR / f"skill_01_data_{ts}.csv"
        csv_path.write_text("\n".join(csv_lines), encoding="utf-8")

        logger.info(
            f"tracking_complete keywords={len(keywords)} total_notes={len(all_search_results)}"
        )

        await self._close_scraper()
        return report
