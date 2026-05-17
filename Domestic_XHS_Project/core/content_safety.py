"""内容安全过滤器 — 小红书违禁词检测 + 玄学赛道安全替换

在生成任何文案后、发布前，强制进行违禁词扫描和替换。
"""

import json
import re
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FORBIDDEN_PATH = _PROJECT_ROOT / "data" / "exports" / "xhs_forbidden_words.json"

# 玄学赛道高危词 → 安全替换
METAPHYSICS_SAFE_MAP = {
    # 迷信高危词替换
    "算命": "命理分析",
    "算卦": "卦象解读",
    "风水": "堪舆",
    "开光": "祝祷加持",
    "转运": "调频",
    "招财": "聚财",
    "招财进宝": "财源汇聚",
    "辟邪": "护身",
    "化煞": "化气",
    "镇宅": "安宅",
    "逢凶化吉": "转危为安",
    "助吉避凶": "趋吉避害",
    "作法": "仪式",
    "还阴债": "化解旧缘",
    "起运": "开运",
    "改命": "调命",
    "逆天改命": "顺势而为",
    "法力无边": "能量充沛",
    "神仙": "古贤",
    "显灵": "应验",
    "灵验": "应验",
    "显圣": "显化",
    # 广告极限词
    "最好": "极佳",
    "第一": "领先",
    "唯一": "唯一",  # 在引经据典语境下可保留
    "最有效": "显著有效",
    "绝对": "确实",
    "肯定": "通常",
    "保证": "经验表明",
    "100%": "十有八九",
    # 医疗功效词
    "治疗": "调理",
    "治愈": "改善",
    "疗效": "功效",
    "药方": "配方",
    "根治": "从根源改善",
    "消炎": "舒缓",
    "杀菌": "净化",
    "排毒": "清理",
    # 消费诱导
    "秒杀": "优选",
    "抢购": "选购",
    "限时": "近期",
    "赶紧买": "可以考虑",
}


class ContentSafetyChecker:
    """内容安全检查器"""

    def __init__(self, forbidden_words_path: Path | None = None):
        self.path = forbidden_words_path or _FORBIDDEN_PATH
        self.high_risk: set[str] = set()
        self.medium_risk: set[str] = set()
        self.low_risk: set[str] = set()
        self._load()

    def _load(self):
        """加载违禁词库"""
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for word in data.get("high_risk", []):
                self.high_risk.add(str(word).strip())
            for word in data.get("medium_risk", []):
                self.medium_risk.add(str(word).strip())
            for word in data.get("low_risk", []):
                self.low_risk.add(str(word).strip())
        except Exception:
            pass

        # 补充玄学赛道特有关键词
        _extra_high = {"算命", "风水", "开光", "转运", "招财", "作法", "逆天改命", "改命"}
        _extra_medium = {"起运", "辟邪", "镇宅", "化煞", "灵验", "显灵"}
        self.high_risk.update(_extra_high)
        self.medium_risk.update(_extra_medium)

    def check(self, text: str) -> dict:
        """扫描文本中的违禁词。

        Returns:
            {
                "score": 100,         # 健康评分 0-100
                "risk_level": "安全", # 安全/低风险/中风险/高风险
                "hits": [],           # 命中的违禁词 [{word, level, position, suggestion}]
                "safe_text": "",      # 替换后的安全文本
            }
        """
        hits = []
        score = 100

        # 高危检查
        for word in self.high_risk:
            if word and word in text:
                pos = text.find(word)
                suggestion = METAPHYSICS_SAFE_MAP.get(word, "建议删除或替换")
                hits.append(
                    {
                        "word": word,
                        "level": "高风险",
                        "position": pos,
                        "suggestion": suggestion,
                    }
                )
                score -= 30

        # 中危检查
        for word in self.medium_risk:
            if word and word in text:
                pos = text.find(word)
                suggestion = METAPHYSICS_SAFE_MAP.get(word, "建议斟酌使用")
                hits.append(
                    {
                        "word": word,
                        "level": "中风险",
                        "position": pos,
                        "suggestion": suggestion,
                    }
                )
                score -= 15

        # 低危检查
        for word in self.low_risk:
            if word and word in text:
                pos = text.find(word)
                hits.append(
                    {
                        "word": word,
                        "level": "低风险",
                        "position": pos,
                        "suggestion": "可保留但建议留意上下文",
                    }
                )
                score -= 5

        score = max(0, min(100, score))

        if score >= 90:
            level = "安全"
        elif score >= 70:
            level = "低风险"
        elif score >= 50:
            level = "中风险"
        else:
            level = "高风险"

        # 生成安全版本
        safe_text = self.sanitize(text)

        return {
            "score": score,
            "risk_level": level,
            "hits": sorted(hits, key=lambda x: x["position"]),
            "safe_text": safe_text,
        }

    def sanitize(self, text: str) -> str:
        """自动替换所有已知违禁词为安全版本"""
        result = text
        # 先替换玄学赛道词
        for bad, good in METAPHYSICS_SAFE_MAP.items():
            if bad in result:
                result = result.replace(bad, good)
        return result

    def quick_check(self, text: str) -> bool:
        """快速检查：是否可直接发布"""
        result = self.check(text)
        return result["score"] >= 90


# 全局单例
_checker: Optional[ContentSafetyChecker] = None


def get_checker() -> ContentSafetyChecker:
    """获取全局安全检查器单例"""
    global _checker
    if _checker is None:
        _checker = ContentSafetyChecker()
    return _checker


def safety_filter(text: str, auto_fix: bool = True) -> dict:
    """便利函数：检查文案安全性

    Args:
        text: 待检查文案
        auto_fix: 是否自动返回修复后版本

    Returns:
        {
            "safe": bool,           # 是否可直接发布
            "score": int,           # 评分
            "risk_level": str,      # 风险等级
            "issues": list[str],    # 问题描述
            "fixed_text": str,      # 修复后文本 (如果 auto_fix=True)
            "original_text": str,   # 原文
        }
    """
    checker = get_checker()
    result = checker.check(text)

    issues = []
    for hit in result["hits"]:
        issues.append(f"[{hit['level']}] '{hit['word']}' → {hit['suggestion']}")

    return {
        "safe": result["score"] >= 90,
        "score": result["score"],
        "risk_level": result["risk_level"],
        "issues": issues,
        "fixed_text": result["safe_text"] if auto_fix else text,
        "original_text": text,
    }
