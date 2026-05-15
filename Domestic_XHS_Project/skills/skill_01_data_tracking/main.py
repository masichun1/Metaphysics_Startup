"""Skill 01 — 数据自动追踪 (Data Auto Tracking)

定时抓取指定关键词或对标账号的数据表现。
OpenCLI 负责爬取，Claude 负责分析趋势和输出优化建议。
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("xhs.skill_01")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"

# 默认追踪关键词
DEFAULT_KEYWORDS = [
    "塔罗测试", "星座运势", "八字命理", "风水布局",
    "水晶功效", "冥想入门", "占卜", "生肖运程",
    "紫微斗数", "面相分析", "手相", "能量疗愈",
]

# 对标账号（示例）
BENCHMARK_ACCOUNTS = [
    "玄学大师姐", "星座达人Lily", "塔罗师小K",
]


class Skill01DataTracking:
    """数据自动追踪 — 定时爬取 + Claude分析"""

    skill_id = "skill_01"
    skill_name = "数据自动追踪"

    def __init__(self, ai_client=None, browser_manager=None, config=None):
        self.ai = ai_client
        self.browser = browser_manager
        self.config = config

    def run(
        self,
        keywords: list[str] | None = None,
        accounts: list[str] | None = None,
        note_count: int = 20,
    ) -> dict:
        """执行数据追踪。

        Args:
            keywords: 要搜索的关键词列表。None 则使用默认列表。
            accounts: 要监控的对标账号列表。
            note_count: 每个关键词/账号抓取多少条笔记。

        Returns:
            结构化数据报告 dict。
        """
        keywords = keywords or DEFAULT_KEYWORDS
        accounts = accounts or BENCHMARK_ACCOUNTS

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "keywords_analysis": [],
            "account_analysis": [],
            "alerts": [],
        }

        # Claude 生成数据采集指令 -> OpenCLI 执行
        for kw in keywords:
            analysis = {
                "keyword": kw,
                "notes_collected": 0,
                "avg_likes": 0,
                "avg_comments": 0,
                "avg_collects": 0,
                "top_note": None,
                "trend_direction": "stable",
                "claude_insight": "",
            }

            if self.ai:
                insight = self.ai.generate_text(
                    user_prompt=f"""分析小红书关键词"{kw}"在玄学赛道的数据表现趋势。
请给出：
1. 该关键词近期热度趋势判断（上升/平稳/下降）
2. 爆款内容特征（标题风格、封面类型、内容结构）
3. 内容创作建议（3条具体可执行建议）

用中文回答，控制在300字以内。"""
                )
                analysis["claude_insight"] = insight

            report["keywords_analysis"].append(analysis)

        for account in accounts:
            analysis = {
                "account": account,
                "recent_notes": 0,
                "avg_engagement": 0,
                "follower_trend": "unknown",
                "content_mix": {},
                "claude_insight": "",
            }

            if self.ai:
                insight = self.ai.generate_text(
                    user_prompt=f"""分析小红书账号"{account}"在玄学赛道的运营策略。
请给出：
1. 账号定位和人设分析
2. 内容矩阵分析（选题类型分布）
3. 可复用的运营技巧（3条）
4. 账号的差异化优势

用中文回答，控制在300字以内。"""
                )
                analysis["claude_insight"] = insight

            report["account_analysis"].append(analysis)

        # Export
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_01_tracking_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("tracking_complete", keywords=len(keywords), accounts=len(accounts))

        return report
