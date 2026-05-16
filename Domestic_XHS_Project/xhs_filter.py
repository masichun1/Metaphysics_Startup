"""小红书内容安全过滤器 — 违禁词检测 + 自动替换

数据来源: GitHub prohibited-word-detection (500+ 违禁词, 15 类别)
整合: 玄学/中医/道学/文创领域专属违禁词
"""

import json
import re
from pathlib import Path

FILTER_DATA = Path(__file__).parent / "data" / "exports" / "xhs_forbidden_words.json"


class XHSContentFilter:
    """小红书内容安全检查 + 违禁词过滤"""

    # 玄学/道学领域额外违禁词（平台敏感 + 可能违规）
    NICHE_FORBIDDEN = [
        # 封建迷信类（最高风险）
        "算命", "改命", "改运", "作法", "驱鬼", "驱邪",
        "鬼上身", "附体", "下蛊", "毒咒", "死咒",
        "包治百病", "药到病除", "神仙", "菩萨保佑",
        # 医疗效果类（中医相关绝不能说的）
        "治愈", "根治", "疗效", "药方", "治疗",
        "处方", "秘方", "千年秘方", "祖传秘方",
        # 引流敏感词
        "加微信", "加V", "扫码", "私聊", "私信我",
        "免费算命", "免费看相", "免费测", "免费咨询",
        # 极具诱导性
        "不转不是", "转发保佑", "不关注就", "不看后悔",
    ]

    # 建议替换词映射
    SAFE_REPLACEMENTS = {
        "算命": "命盘分析",
        "改命": "调整运势",
        "改运": "提升能量",
        "作法": "能量仪式",
        "驱鬼": "清理能量",
        "驱邪": "净化气场",
        "治愈": "改善",
        "根治": "调理",
        "疗效": "体验",
        "药方": "方案",
        "治疗": "调整",
        "秘方": "传统方法",
        "千年秘方": "传统智慧方法",
        "祖传秘方": "传承方法",
        "包治百病": "综合调理",
        "药到病除": "帮助改善",
    }

    def __init__(self):
        self.high_risk = []
        self.medium_risk = []
        self.low_risk = []
        self._load_dictionary()

    def _load_dictionary(self):
        """加载违禁词库"""
        if FILTER_DATA.exists():
            data = json.loads(FILTER_DATA.read_text(encoding="utf-8"))
            self.high_risk = data.get("high_risk", [])
            self.medium_risk = data.get("medium_risk", [])
            self.low_risk = data.get("low_risk", [])

        if not self.high_risk:
            # Fallback: embedded minimal word list
            self.high_risk = [
                "国家级", "世界级", "最高级", "第一", "唯一", "首选", "最好",
                "顶级", "极品", "最", "第一品牌", "金牌", "最受欢迎", "销量第一",
                "根治", "治愈", "包治百病", "永不复发", "特效", "神药",
                "点击领取", "免费领取", "转发", "不转不是", "加微信", "微信号",
            ]

    def check(self, text: str) -> dict:
        """检查文本是否包含违禁词

        Returns:
            dict with: has_risk (bool), risk_level (str), matches (list), suggestions (list)
        """
        matches = []
        risk_level = "safe"

        # 检查高风险词
        for word in self.high_risk:
            if word in text:
                matches.append({"word": word, "level": "high"})
                risk_level = "high"

        # 检查中风险词
        for word in self.medium_risk:
            if word in text:
                matches.append({"word": word, "level": "medium"})
                if risk_level == "safe":
                    risk_level = "medium"

        # 检查领域专属词
        for word in self.NICHE_FORBIDDEN:
            if word in text:
                matches.append({"word": word, "level": "high", "source": "niche"})
                risk_level = "high"

        # 检查低风险词
        for word in self.low_risk:
            if word in text:
                matches.append({"word": word, "level": "low"})

        # 生成替换建议
        suggestions = []
        for m in matches:
            word = m["word"]
            if word in self.SAFE_REPLACEMENTS:
                suggestions.append({"original": word, "replacement": self.SAFE_REPLACEMENTS[word]})

        return {
            "has_risk": len(matches) > 0,
            "risk_level": risk_level,
            "match_count": len(matches),
            "matches": matches[:20],
            "suggestions": suggestions,
        }

    def sanitize(self, text: str) -> str:
        """自动替换文本中的违禁词为安全词

        Returns:
            替换后的安全文本
        """
        result = text
        for forbidden, safe in self.SAFE_REPLACEMENTS.items():
            if forbidden in result:
                result = result.replace(forbidden, safe)
        return result

    def check_post(self, title: str, body: str, tags: list[str]) -> dict:
        """检查整篇笔记（标题+正文+标签）"""
        full_text = f"{title} {body} {' '.join(tags)}"
        result = self.check(full_text)

        # 分类检查
        title_check = self.check(title)
        tag_check = self.check(' '.join(tags))

        return {
            "overall": result,
            "title": title_check,
            "tags": tag_check,
            "safe_to_publish": result["risk_level"] != "high",
            "needs_review": result["risk_level"] == "medium",
            "sanitized_title": self.sanitize(title) if title_check["has_risk"] else title,
            "sanitized_body": self.sanitize(body) if result["has_risk"] else body,
            "sanitized_tags": [self.sanitize(t) for t in tags] if tag_check["has_risk"] else tags,
        }


# 快速检测函数
def quick_check(text: str) -> bool:
    """快速检测文本是否安全 (True=安全, False=有风险)"""
    f = XHSContentFilter()
    return not f.check(text)["has_risk"]


if __name__ == "__main__":
    # 测试
    f = XHSContentFilter()

    test_cases = [
        "这个水晶真的很好，治愈了我的失眠",
        "道家修行入门的三个小方法，改运从今天开始",
        "今天给大家分享一下中医养生的小妙招，调理气血效果最好",
        "加微信免费算命，驱鬼作法包治百病",
        "每日一悟：上善若水，水善利万物而不争",
    ]

    for text in test_cases:
        result = f.check(text)
        status = "SAFE" if not result["has_risk"] else f"RISK-{result['risk_level']}"
        print(f"[{status}] {text[:60]}...")
        if result["matches"]:
            print(f"  Matches: {[m['word'] for m in result['matches'][:5]]}")
        if result["suggestions"]:
            print(f"  Suggestions: {result['suggestions']}")
        print()
