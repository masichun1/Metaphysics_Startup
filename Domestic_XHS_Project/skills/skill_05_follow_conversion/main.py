"""Skill 05 — 引导关注 (Follow Conversion)

根据不同场景，生成自然且高转化的引流话术策略。
Claude 生成多版本话术库 -> OpenCLI 辅助自动回复（严格控制频率，避免风控）。
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("xhs.skill_05")

_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class Skill05FollowConversion:
    """引导关注 — 话术库生成 + 转化策略"""

    skill_id = "skill_05"
    skill_name = "引导关注"

    # 高转化场景模板
    SCENARIOS = [
        "评论区互动 -> 引导关注",
        "私信咨询 -> 引导关注 + 转化",
        "笔记结尾 CTA -> 关注/收藏引导",
        "直播互动 -> 实时转化",
        "主页访问 -> 初次印象引导",
    ]

    def __init__(self, ai_client=None, browser_manager=None, config=None):
        self.ai = ai_client
        self.browser = browser_manager
        self.config = config

    def run(
        self,
        niche: str = "塔罗占卜",
        account_style: str = "专业温暖型",
        target_audience: str = "25-40岁对玄学好奇的女性",
    ) -> dict:
        """生成引导关注话术库和转化策略。

        Args:
            niche: 赛道。
            account_style: 账号风格（专业温暖型/神秘高冷型/接地气搞怪型）。
            target_audience: 目标用户画像描述。

        Returns:
            话术库和策略方案 dict。
        """
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "niche": niche,
            "account_style": account_style,
            "target_audience": target_audience,
            "scripts_by_scenario": {},  # 按场景分类的话术
            "safety_guidelines": [],  # 安全执行规范
            "claude_strategy": "",
        }

        # Claude generates the full strategy
        if self.ai:
            prompt = f"""你是小红书{niche}赛道的转化运营专家。请为以下账号生成引导关注话术库。

账号赛道：{niche}
账号风格：{account_style}
目标用户：{target_audience}

请为以下5个场景分别生成3条自然、高转化的话术（中文，800字以内）：

1. 【评论区互动】用户评论后，回复引导关注
   要求：不要硬广，先提供价值再引导关注
   示例场景：用户说"好准！" / 用户提问 / 用户表示感兴趣

2. 【私信咨询】用户私信咨询时的转化话术
   要求：专业+温暖，先回答问题再自然引导

3. 【笔记结尾CTA】每篇笔记结尾的关注/收藏引导
   要求：自然、简洁、与内容相关
   避免："关注我"这种生硬表达

4. 【直播话术】直播中的实时互动转化
   要求：节奏感强、互动感强、制造FOMO

5. 【主页简介】账号主页的简介话术优化
   要求：一句话说清楚"我是谁+关注我能获得什么"

同时给出：
- 防封号安全执行规范（回复频率、时间间隔、每日上限）
- 不同用户画像的差异化话术策略"""

            try:
                report["claude_strategy"] = self.ai.generate_text(
                    user_prompt=prompt,
                    max_tokens=2500,
                )
            except Exception as e:
                logger.error("claude_strategy_failed", error=str(e))

        # Safety execution guidelines (always included)
        report["safety_guidelines"] = [
            {
                "rule": "回复频率控制",
                "detail": "每小时最多回复5条评论，每天最多回复30条",
                "reason": "模拟正常用户行为，避免触发小红书反营销机制",
            },
            {
                "rule": "时间随机化",
                "detail": "每条回复之间间隔 2-8 分钟，加入随机抖动",
                "reason": "固定频率容易被判定为机器人",
            },
            {
                "rule": "内容多样化",
                "detail": "同类话术不连续使用超过3次，定期轮换话术模板",
                "reason": "重复内容触发重复内容检测",
            },
            {
                "rule": "先互动后引导",
                "detail": "至少先与用户有2-3轮真实互动后再发引导关注话术",
                "reason": "赤裸裸的引流会被举报",
            },
            {
                "rule": "敏感词规避",
                "detail": "避免使用'加微信'、'扫码'、'私聊'等直接引流词，用'主页'、'看简介'等小红书原生表达",
                "reason": "小红书对站外引流零容忍",
            },
            {
                "rule": "异常熔断",
                "detail": "连续收到系统警告或评论被删除时，自动暂停24小时",
                "reason": "防止账号被限流或封禁",
            },
        ]

        # Build manual script library as fallback
        if not self.ai:
            report["scripts_by_scenario"] = self._get_fallback_scripts(niche)

        # Export
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = _EXPORT_DIR / f"skill_05_conversion_{ts}.json"
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("conversion_scripts_generated", niche=niche)

        return report

    @staticmethod
    def _get_fallback_scripts(niche: str) -> dict:
        """Fallback script library without AI."""
        return {
            "comment_reply": [
                {
                    "trigger": "用户说好准/太对了",
                    "reply": f"谢谢宝子认可！主页还有更多{niche}干货，每天更新哦~有问题欢迎随时问我",
                },
                {
                    "trigger": "用户提问",
                    "reply": f"这个问题问得好！我主页有篇笔记专门讲这个，建议配合那篇一起看~",
                },
                {
                    "trigger": "用户表示有兴趣",
                    "reply": f"看来你也对{niche}感兴趣呀！主页有系统的入门指南，少走弯路~",
                },
            ],
            "note_cta": [
                f"觉得有用的话，点个收藏慢慢看~每天分享{niche}小知识，关注不迷路",
                f"你遇到过这种情况吗？评论区聊聊，明天更新相关话题",
                f"主页还有更多{niche}干货，已经帮你整理好了",
            ],
            "profile_bio": [
                f"专注{niche} | 每天分享一个玄学小知识 | 帮你找到人生答案",
                f"从不迷信，只信科学{niche} | 主页有惊喜 | 私信可约",
                f"用最简单的方式讲{niche} | 关注我，一起成长",
            ],
        }
