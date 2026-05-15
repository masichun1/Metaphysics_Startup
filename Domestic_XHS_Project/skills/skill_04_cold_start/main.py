"""Skill 04 — 新号冷启动辅助 (New Account Cold Start)

基于竞品分析结果，生成高点击率的起号选题库和文案框架。
Claude 基于竞品数据生成选题库和文案模板 -> OpenCLI 辅助批量创建草稿。
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("xhs.skill_04")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill04ColdStart:
    """新号冷启动 — 选题库生成 + 内容规划"""

    skill_id = "skill_04"
    skill_name = "新号冷启动辅助"

    def __init__(self, ai_client=None, browser_manager=None, config=None):
        self.ai = ai_client
        self.browser = browser_manager
        self.config = config

    def run(
        self,
        niche: str = "塔罗占卜",
        account_positioning: str = "",
        competitor_insights: dict | None = None,
        days: int = 30,
    ) -> dict:
        """生成新号冷启动方案。

        Args:
            niche: 细分赛道（如"塔罗占卜"、"星座情感"、"风水布局"）。
            account_positioning: 账号定位描述。
            competitor_insights: Skill 03 的竞品调研结果，用于基于数据生成策略。
            days: 规划天数。

        Returns:
            冷启动方案 dict，包含选题库、文案框架、发布日历。
        """
        if not account_positioning:
            account_positioning = f"专业{niche}师，用温暖易懂的方式分享{niche}知识，帮助粉丝获得生活指引"

        plan = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "niche": niche,
            "account_positioning": account_positioning,
            "planning_days": days,
            "content_calendar": [],  # 每日选题
            "headline_templates": [],  # 标题模板库
            "cover_style_guide": "",  # 封面风格指南
            "posting_schedule": {},  # 发布时间建议
            "first_week_sprints": [],  # 第一周冲刺计划
        }

        # Claude-generated cold start strategy
        if self.ai:
            plan = self._generate_strategy(niche, account_positioning, days, competitor_insights)
        else:
            plan["content_calendar"] = self._generate_basic_calendar(niche, days)

        # Export
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_04_cold_start_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("cold_start_plan_generated", niche=niche, days=days)

        return plan

    def _generate_strategy(
        self,
        niche: str,
        positioning: str,
        days: int,
        competitor_insights: dict | None,
    ) -> dict:
        """Use Claude to generate a comprehensive cold start strategy."""
        competitor_context = ""
        if competitor_insights:
            competitor_context = f"""
竞品分析结果：
{json.dumps(competitor_insights.get('viral_formulas', [])[:5], ensure_ascii=False, indent=2)}
"""

        prompt = f"""你是一位小红书玄学赛道运营专家。现在需要为一个新号制定冷启动策略。

赛道：{niche}
账号定位：{positioning}
规划天数：{days}
{competitor_context}

请制定一个完整的冷启动方案，包含以下内容（中文，1200字以内）：

1. 【账号人设设计】账号名建议、简介文案（3版）、头像/背景风格建议
2. 【第一周冲刺计划】每天发布什么内容，为什么这样安排
3. 【选题矩阵】按"流量款/涨粉款/成交款"三类各给5个选题
4. 【标题模板库】5个高点击率标题模板（可直接套用）
5. 【发布时间策略】每周哪天、每天几点发布效果最好（玄学赛道）
6. 【封面风格指南】封面设计的核心原则和参考方向
7. 【风险提示】新号前30天要避免的3个常见错误"""

        try:
            analysis = self.ai.generate_text(
                user_prompt=prompt,
                max_tokens=3000,
            )
        except Exception as e:
            logger.error("claude_strategy_failed", error=str(e))
            analysis = "AI 策略生成暂不可用，请稍后重试。"

        content_calendar = self._generate_basic_calendar(niche, min(days, 14))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "niche": niche,
            "account_positioning": positioning,
            "planning_days": days,
            "claude_strategy": analysis,
            "content_calendar": content_calendar,
            "headline_templates": [
                {"type": "悬念型", "template": f"做了{{X}}年{niche}，我发现{{一个反常识结论}}"},
                {"type": "数字型", "template": f"{niche}必备的{{N}}个{{工具/方法}}，建议收藏"},
                {"type": "情感型", "template": f"{{星座}}的你，最近在为什么焦虑？{niche}告诉你答案"},
                {"type": "干货型", "template": f"新手学{niche}，90%的人都卡在{{痛点}}"},
                {"type": "故事型", "template": f"一个客户的真实故事：{niche}改变了她的人生"},
            ],
            "posting_schedule": {
                "best_days": ["周一", "周三", "周五", "周日"],
                "best_times": ["8:00-9:00", "12:00-13:00", "18:00-19:00", "21:00-22:00"],
                "frequency": "每天1-2篇，前期坚持日更",
            },
        }

    @staticmethod
    def _generate_basic_calendar(niche: str, days: int) -> list[dict]:
        """Generate a basic content calendar without AI."""
        content_types = [
            "入门科普", "个人故事", "干货教程", "互动问答",
            "案例分享", "玄学知识", "产品种草", "热点借势",
        ]
        calendar = []
        for i in range(days):
            ct = content_types[i % len(content_types)]
            calendar.append({
                "day": i + 1,
                "content_type": ct,
                "topic_hint": f"{niche}相关{ct}内容",
                "notes": f"第{i+1}天发布{ct}类内容，建立初期内容矩阵",
            })
        return calendar
