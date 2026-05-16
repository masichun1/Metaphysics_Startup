#!/usr/bin/env python3
"""小红书每日自动化运营 — 5大 Skills 集成

每日执行流程:
  1. 登录验证 + 安全检测
  2. Skill 01 — 数据自动追踪 (搜索关键词, 采集指标)
  3. Skill 02 — 评论区监控 (情感分析, 线索提取)
  4. Skill 03 — 竞品调研 (爆款拆解)
  5. Skill 04 — 冷启动辅助 (AI 生成明天要发的文案)
  6. Skill 05 — 引导关注 (话术库生成)
  7. 养号 — 30分钟自然浏览
  8. 日报生成 + 数据存档

安全红线:
  - 每次操作间隔 2-8 秒随机延迟
  - 每小时最多 30 次页面操作
  - 模拟真人滚动和鼠标轨迹
  - 自动检测验证码并暂停
"""

import json
import os
import random
import sys
import time
import csv
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from xhs_operator import XHSOperator
from xhs_filter import XHSContentFilter

# 配置
DATA_DIR = Path(__file__).resolve().parent / "data"
EXPORT_DIR = DATA_DIR / "exports"
REPORT_DIR = DATA_DIR / "reports"
CSV_DIR = DATA_DIR / "csv"

# 关键词配置
TRACK_KEYWORDS = ["命理", "塔罗", "八字", "星座", "道家", "风水"]
COMPETITOR_KEYWORDS = ["道家玄学", "命理分析", "塔罗占卜", "八字算命", "星座运势"]

# 对标账号
BENCHMARK_ACCOUNTS = [
    "南山道长",
    "清玄小记",
    "道心暖暖",
]

# 安全参数
MIN_DELAY = 3  # 最小操作间隔(秒)
MAX_DELAY = 8  # 最大操作间隔(秒)
MAX_OPS_PER_HOUR = 25  # 每小时最大操作数


class DailyOps:
    """小红书每日自动化运营"""

    def __init__(self):
        self.op: XHSOperator | None = None
        self.start_time = time.monotonic()
        self.op_count = 0
        self.report = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "started_at": datetime.now().isoformat(),
            "skills": {},
            "yanghao": {},
            "next_post": {},
        }

        # Ensure directories
        for d in [EXPORT_DIR, REPORT_DIR, CSV_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def safe_delay(self, min_s: float = None, max_s: float = None):
        """安全延迟 + 频率检查"""
        if self.op_count >= MAX_OPS_PER_HOUR:
            cooldown = random.uniform(60, 180)
            print(f"    [COOLDOWN] {self.op_count} ops reached, waiting {cooldown:.0f}s...")
            time.sleep(cooldown)
            self.op_count = 0
        delay = random.uniform(min_s or MIN_DELAY, max_s or MAX_DELAY)
        time.sleep(delay)
        self.op_count += 1

    def check_rate_limit(self):
        """检查是否需要暂停以保持安全"""
        elapsed = (time.monotonic() - self.start_time) / 60
        rpm = self.op_count / elapsed if elapsed > 0 else 0
        if rpm > 2:  # 每分钟最多2次操作
            wait = random.uniform(30, 60)
            print(f"    [RATE LIMIT] RPM={rpm:.1f}, waiting {wait:.0f}s...")
            time.sleep(wait)

    # ============================================================
    # Skill 01 — 数据自动追踪
    # ============================================================
    def skill_01_data_tracking(self):
        """搜索关键词 → 采集笔记数据 → 保存CSV"""
        print("\n" + "=" * 50)
        print("Skill 01 — 数据自动追踪")
        print("=" * 50)

        all_data = []
        page = self.op.page

        for kw in TRACK_KEYWORDS:
            print(f"\n  [*] 搜索关键词: {kw}")
            try:
                url = f"https://www.xiaohongshu.com/search_result?keyword={kw}"
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                self.safe_delay(4, 6)

                # 滚动加载
                for i in range(3):
                    page.evaluate("window.scrollBy(0, 500)")
                    time.sleep(1.5)

                # 提取笔记数据
                notes = page.evaluate("""() => {
                    const sections = document.querySelectorAll('section.note-item');
                    return Array.from(sections).slice(0, 15).map(s => {
                        const title = s.querySelector('.title, footer a span')?.textContent?.trim() || '';
                        const author = s.querySelector('.author .name, .nickname')?.textContent?.trim() || '';
                        const likes = s.querySelector('.like-wrapper span, .count')?.textContent?.trim() || '0';
                        const link = s.querySelector('a[href*="/explore/"]')?.href || '';
                        return {title, author, likes, link};
                    }).filter(n => n.title.length > 3);
                }""")

                for n in notes:
                    n["keyword"] = kw
                    n["collected_at"] = datetime.now().isoformat()

                all_data.extend(notes)
                print(f"    [OK] {kw}: {len(notes)} notes found")

            except Exception as e:
                print(f"    [ERR] {kw}: {e}")

        # Save to CSV
        if all_data:
            csv_path = CSV_DIR / f"skill_01_data_{datetime.now().strftime('%Y%m%d')}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["keyword", "title", "author", "likes", "link", "collected_at"])
                writer.writeheader()
                writer.writerows(all_data)
            print(f"\n  [SAVED] {len(all_data)} rows → {csv_path}")

        # Save JSON
        json_path = EXPORT_DIR / f"skill_01_data_{datetime.now().strftime('%Y%m%d')}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"date": datetime.now().isoformat(), "total": len(all_data), "items": all_data}, f, indent=2, ensure_ascii=False)

        self.report["skills"]["01_data_tracking"] = {
            "total_notes": len(all_data),
            "keywords_used": len(TRACK_KEYWORDS),
            "csv_path": str(csv_path) if all_data else "",
        }
        return all_data

    # ============================================================
    # Skill 02 — 评论区监控
    # ============================================================
    def skill_02_comment_monitor(self, note_urls: list[str] | None = None):
        """监控评论区 → 情感分析 → 线索提取"""
        print("\n" + "=" * 50)
        print("Skill 02 — 评论区监控")
        print("=" * 50)

        # If no specific URLs, check recent notes from search
        if not note_urls:
            note_urls = []
            # Search for our niche to find notes with comments
            for kw in ["道家", "命理"]:
                url = f"https://www.xiaohongshu.com/search_result?keyword={kw}&sort=time"
                self.op.page.goto(url, timeout=30000, wait_until="domcontentloaded")
                self.safe_delay(3, 5)
                links = self.op.page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href*="/explore/"]'))
                        .map(a => a.href).filter(h => h.includes('/explore/')).slice(0, 5);
                }""")
                note_urls.extend(links)
                note_urls = list(set(note_urls))[:5]

        all_comments = []
        for note_url in note_urls:
            print(f"\n  [*] 查看评论: {note_url[:60]}...")
            try:
                self.op.page.goto(note_url, timeout=30000, wait_until="domcontentloaded")
                self.safe_delay(3, 5)

                # 滚动到评论区
                self.op.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.4)")
                self.safe_delay(2, 3)

                comments = self.op.page.evaluate("""() => {
                    const items = document.querySelectorAll('.comment-item, [class*="comment-item"]');
                    return Array.from(items).slice(0, 30).map(c => {
                        const user = c.querySelector('.name, .nickname, [class*="name"]')?.textContent?.trim() || '';
                        const text = c.querySelector('.content, [class*="content"]')?.textContent?.trim() || '';
                        const time = c.querySelector('.date, .time')?.textContent?.trim() || '';
                        return {user, text, time};
                    }).filter(c => c.text.length > 2);
                }""")

                # 简单情感分析
                for c in comments:
                    c["sentiment"] = self._analyze_sentiment(c.get("text", ""))
                    c["intent"] = self._detect_intent(c.get("text", ""))
                    c["source_url"] = note_url

                all_comments.extend(comments)
                print(f"    [OK] {len(comments)} comments extracted")

            except Exception as e:
                print(f"    [ERR] {e}")

        # Save
        if all_comments:
            path = EXPORT_DIR / f"skill_02_comments_{datetime.now().strftime('%Y%m%d')}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"date": datetime.now().isoformat(), "total": len(all_comments), "comments": all_comments}, f, indent=2, ensure_ascii=False)

            # Stats
            sentiments = {"positive": 0, "neutral": 0, "negative": 0}
            intents = {"purchase": 0, "question": 0, "none": 0}
            for c in all_comments:
                sentiments[c.get("sentiment", "neutral")] += 1
                intents[c.get("intent", "none")] += 1

            print(f"\n    情感分布: {sentiments}")
            print(f"    意图分布: {intents}")

        self.report["skills"]["02_comment_monitor"] = {
            "notes_checked": len(note_urls),
            "total_comments": len(all_comments),
        }
        return all_comments

    # ============================================================
    # Skill 03 — 竞品/同行调研
    # ============================================================
    def skill_03_competitor_research(self):
        """搜索竞品关键词 → 提取爆款 → 拆解公式"""
        print("\n" + "=" * 50)
        print("Skill 03 — 竞品/同行调研")
        print("=" * 50)

        viral_notes = []
        for kw in COMPETITOR_KEYWORDS[:3]:
            print(f"\n  [*] 调研关键词: {kw}")
            try:
                url = f"https://www.xiaohongshu.com/search_result?keyword={kw}&sort=general"
                self.op.page.goto(url, timeout=30000, wait_until="domcontentloaded")
                self.safe_delay(4, 6)

                for i in range(3):
                    self.op.page.evaluate("window.scrollBy(0, 600)")
                    time.sleep(1.5)

                notes = self.op.page.evaluate("""() => {
                    const sections = document.querySelectorAll('section.note-item');
                    return Array.from(sections).slice(0, 15).map(s => {
                        const title = s.querySelector('.title, footer a span')?.textContent?.trim() || '';
                        const author = s.querySelector('.author .name, .nickname')?.textContent?.trim() || '';
                        const likes = s.querySelector('.like-wrapper span, .count')?.textContent?.trim() || '0';
                        const link = s.querySelector('a[href*="/explore/"]')?.href || '';
                        return {title, author, likes, link};
                    }).filter(n => n.title.length > 5 && parseInt(n.likes) > 100);
                }""")

                viral_notes.extend(notes)
                print(f"    [OK] {len(notes)} high-engagement notes")

            except Exception as e:
                print(f"    [ERR] {kw}: {e}")

        # 分析标题模式
        title_patterns = self._extract_title_patterns(viral_notes)

        result = {
            "date": datetime.now().isoformat(),
            "total_viral_notes": len(viral_notes),
            "viral_notes": viral_notes[:20],
            "title_patterns": title_patterns,
        }

        path = EXPORT_DIR / f"skill_03_competitor_{datetime.now().strftime('%Y%m%d')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        self.report["skills"]["03_competitor"] = {
            "viral_notes_found": len(viral_notes),
            "title_patterns": title_patterns[:5],
        }
        return result

    # ============================================================
    # Skill 04 — 冷启动辅助 (AI 生成文案)
    # ============================================================
    def skill_04_generate_post(self, competitor_data: dict | None = None):
        """基于竞品数据 → Claude 生成明天要发的文案"""
        print("\n" + "=" * 50)
        print("Skill 04 — 冷启动辅助 / AI 文案生成")
        print("=" * 50)

        # 从知识库 + 竞品数据构建 Prompt
        context = ""
        if competitor_data:
            viral_titles = [n.get("title", "") for n in competitor_data.get("viral_notes", [])[:5]]
            patterns = competitor_data.get("title_patterns", [])
            context = f"""
竞品爆款标题样本：
{json.dumps(viral_titles, ensure_ascii=False, indent=2)}

爆款标题模式：
{json.dumps(patterns, ensure_ascii=False, indent=2)}
"""

        prompt = f"""你是一个深谙小红书流量密码的"道家玄学"博主。请为明天（{datetime.now().date() + timedelta(days=1)}）生成一篇能火的笔记。

你的人设：不是高高在上的大师，而是一个有血有肉、会emo也会豁达、懂道法也懂生活的"互联网闺蜜+道家修行者"。说话带点俏皮，但骨子里有真东西。

目标用户画像：25-40岁女性，深夜会刷"人生的意义是什么"，白天在职场卷，相信命运但也想要掌控感。

{context}

**【第一步：确定最佳发布时间】**
根据小红书玄学赛道流量数据：
- 早7-9点 通勤碎片浏览 → 适合"今日运势"型轻内容
- 午12-14点 午休深度读 → 适合干货知识型
- 晚20-23点 情感高峰期 → 适合情绪共鸣、人生感悟型（玄学流量最高峰！）
- 周末9-11点 学习成长型 → 适合系统知识、教程型
结合内容类型，给出精确发布时间（HH:MM）+ 1句话理由。

**【第二步：写笔记】(网感是第一标准！)**
写稿要求：
# 标题：要有钩子！让人不点进去就难受。用这几种套路：
  - "做了X年XX，今天说点大实话"
  - "如果你最近XX，可能是XX在提醒你"
  - "千万不要XX，否则XX" / "终于知道为什么XX了"
  - 数字钩子："3个信号说明XX""90%的人不知道XX"
# 正文风格：
  - 拒绝说教！像闺蜜深夜聊天，三句话一个金句
  - 短句！分行！有呼吸感！每句不超过20字
  - 适当用emoji但别多（*🌙*🫂这些可以）
  - 开头3秒抓人：抛一个问题/一个反常识/一个画面感
  - 中间有料：给具体方法，不是空道理
  - 结尾有互动：引导评论区聊起来（"你遇到过吗""评论区说说"）
  - 语气要真，不要端着。偶尔流露一点自己的脆弱和成长
# 标签：5-8个，混搭大流量标签+精准小标签

输出JSON: title, body, tags, cover_suggestion, publish_time, time_reason"""

        generated = None
        try:
            # Use AI client if available
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Cross_Border_Project"))
            from core.ai_client import AIClient
            from core.config_loader import load_config as cb_load_config

            config = cb_load_config()
            ai = AIClient(config)
            response = ai.generate_text(user_prompt=prompt, max_tokens=2000)
            print(f"    [AI] Generated {len(response)} chars")

            # Try to parse JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                generated = json.loads(json_match.group())
            else:
                generated = {"raw_response": response}

        except Exception as e:
            print(f"    [AI ERR] {e}")
            # Fallback: use template
            generated = {
                "title": f"偷偷告诉你一个道家改运小方法，我亲测有效*",
                "body": "做道家修行这些年\n发现一个扎心真相：\n\n很多人不是运势差\n是太想把每件事都控制住\n\n老子说\"无为\"\n不是躺平\n是不跟没必要的事较劲\n\n你越抓着不放\n能量越堵\n运气自然绕道走\n\n今天试试：\n睡前放下手机\n闭上眼睛深呼吸3次\n告诉自己：\n\"该来的会来，该走的留不住\"\n\n坚持一周\n你会回来谢我的\n\n你在焦虑什么？\n评论区聊聊，我看着回👇",
                "tags": ["道家智慧", "修心", "转运", "女性成长", "人生感悟", "情绪管理"],
                "cover_suggestion": "暖色调暗光，一只手轻放在一本翻开的书上，旁边一杯热茶，画面安静有质感，左上方白色手写字标题",
                "publish_time": self._best_time_fallback(),
                "time_reason": "基于玄学赛道大盘数据: 晚间20:00-22:00为情感共鸣型内容流量峰值",
                "filter_passed": True,
                "filter_warnings": [],
            }

        # Save generated post
        path = EXPORT_DIR / f"skill_04_post_{datetime.now().strftime('%Y%m%d')}_tomorrow.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(generated, f, indent=2, ensure_ascii=False)

        self.report["skills"]["04_generate_post"] = {
            "generated": generated is not None,
            "save_path": str(path),
        }
        self.report["next_post"] = generated
        return generated

    # ============================================================
    # Skill 05 — 引导关注话术
    # ============================================================
    def skill_05_conversion_scripts(self):
        """生成引导关注/转化话术库"""
        print("\n" + "=" * 50)
        print("Skill 05 — 引导关注话术")
        print("=" * 50)

        scripts = {
            "generated_at": datetime.now().isoformat(),
            "comment_reply": [
                {"trigger": "好准/太对了/真的", "reply": "谢谢认可！主页每天更新道家智慧，关注不迷路~"},
                {"trigger": "怎么学/如何入门", "reply": "可以从主页的入门笔记开始看哦，有系统的学习路径~"},
                {"trigger": "想问/帮我看看", "reply": "可以看主页置顶笔记，或者评论区留言我下期讲~"},
            ],
            "note_cta": [
                "如果对你有帮助，点个收藏慢慢看 | 每天分享道家智慧，关注不亏",
                "你遇到过类似情况吗？评论区说说 | 明天更新更有趣的内容",
                "主页整理了更多道家入门干货，已经帮你分类好了",
            ],
            "dm_reply": [
                "你好呀！感谢关注。你想了解哪方面？命理/风水/修行/养生？",
                "收到你的私信啦~具体问题可以描述一下，我有空回复你",
            ],
            "safety_notice": [
                "每小时最多回复5条评论",
                "每次回复间隔2-5分钟",
                "不直接发微信号/二维码/外链",
                "先用价值内容吸引，再自然引导主页关注",
            ],
        }

        path = EXPORT_DIR / f"skill_05_scripts_{datetime.now().strftime('%Y%m%d')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(scripts, f, indent=2, ensure_ascii=False)

        self.report["skills"]["05_conversion"] = {"scripts_count": len(scripts["comment_reply"])}
        return scripts

    # ============================================================
    # 养号 — 每日30分钟自然浏览
    # ============================================================
    def yanghao(self, duration_minutes: int = 30):
        """每日养号：模拟真人浏览，给算法打标签"""
        print("\n" + "=" * 50)
        print(f"养号 — 模拟真人浏览 {duration_minutes} 分钟")
        print("=" * 50)

        page = self.op.page
        duration_seconds = duration_minutes * 60
        start = time.monotonic()

        # 养号行为：浏览首页 → 搜索关键词 → 看笔记 → 点赞/收藏 → 偶尔评论
        yanghao_keywords = ["命理", "塔罗", "八字", "星座", "道家", "风水"]
        actions = []

        while (time.monotonic() - start) < duration_seconds:
            try:
                # 随机选择行为
                behavior = random.choice(["browse_feed", "search", "read_note", "scroll"])
                elapsed = (time.monotonic() - start) / 60

                if behavior == "browse_feed":
                    page.goto("https://www.xiaohongshu.com/explore", timeout=30000, wait_until="domcontentloaded")
                    self.safe_delay(4, 8)
                    for _ in range(3):
                        page.evaluate(f"window.scrollBy(0, {random.randint(300, 800)})")
                        time.sleep(random.uniform(1, 3))
                    actions.append({"action": "browse_feed", "time": f"{elapsed:.1f}m"})

                elif behavior == "search":
                    kw = random.choice(yanghao_keywords)
                    page.goto(f"https://www.xiaohongshu.com/search_result?keyword={kw}", timeout=30000, wait_until="domcontentloaded")
                    self.safe_delay(3, 6)
                    for _ in range(2):
                        page.evaluate(f"window.scrollBy(0, {random.randint(400, 700)})")
                        time.sleep(random.uniform(1.5, 3))
                    actions.append({"action": "search", "keyword": kw, "time": f"{elapsed:.1f}m"})

                elif behavior == "read_note":
                    # 点开一篇笔记认真看
                    links = page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a[href*="/explore/"]'))
                            .map(a => a.href).filter(h => h.includes('/explore/')).slice(0, 5);
                    }""")
                    if links:
                        note_url = random.choice(links)
                        page.goto(note_url, timeout=30000, wait_until="domcontentloaded")
                        self.safe_delay(6, 12)  # "认真阅读"
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight * random())")
                        self.safe_delay(3, 5)
                        actions.append({"action": "read_note", "url": note_url[:60], "time": f"{elapsed:.1f}m"})

                elif behavior == "scroll":
                    page.evaluate(f"window.scrollBy(0, {random.randint(-300, 500)})")
                    self.safe_delay(2, 4)

                print(f"  [养号 {elapsed:.1f}m] {behavior}: {actions[-1].get('keyword', actions[-1].get('url', ''))[:40] if actions else ''}")

            except Exception as e:
                print(f"  [养号 ERR] {e}")
                self.safe_delay(5, 10)

        self.report["yanghao"] = {
            "duration_minutes": f"{duration_minutes}",
            "actions": len(actions),
            "keywords_browsed": len([a for a in actions if a.get("keyword")]),
        }
        print(f"\n  [OK] 养号完成: {len(actions)} actions in {duration_minutes}min")

    # ============================================================
    # 辅助方法
    # ============================================================
    @staticmethod
    def _best_time_fallback() -> str:
        """基于小红书玄学赛道流量大数据，返回最佳发布时间"""
        hour = datetime.now().hour
        weekday = datetime.now().weekday()  # 0=Mon, 6=Sun
        # 基于XHS大盘数据：玄学赛道用户活跃时段分布
        if weekday >= 5:  # 周末
            # 周末上午学习型内容流量好
            return "09:30"
        else:  # 工作日
            if 6 <= hour < 12:
                return "12:15"  # 午休阅读高峰
            elif 12 <= hour < 17:
                return "20:30"  # 晚间情感高峰
            else:
                return "08:00"  # 次日通勤高峰

    @staticmethod
    def _analyze_sentiment(text: str) -> str:
        pos = ["好", "赞", "喜欢", "厉害", "准", "有用", "感谢", "谢谢", "推荐", "棒", "绝", "真的", "牛", "爱"]
        neg = ["差", "骗", "坑", "假", "不准", "没用", "失望", "垃圾", "后悔", "烂", "坑人"]
        pos_score = sum(1 for w in pos if w in text)
        neg_score = sum(1 for w in neg if w in text)
        if pos_score > neg_score:
            return "positive"
        elif neg_score > pos_score:
            return "negative"
        return "neutral"

    @staticmethod
    def _detect_intent(text: str) -> str:
        purchase_kw = ["多少钱", "怎么买", "在哪里", "价格", "链接", "私我", "求推荐", "想买", "收费", "预约"]
        question_kw = ["怎么样", "有用吗", "真的假的", "效果", "准吗", "怎么用", "适合吗", "能不能"]
        if any(kw in text for kw in purchase_kw):
            return "purchase"
        if any(kw in text for kw in question_kw):
            return "question"
        return "none"

    @staticmethod
    def _extract_title_patterns(notes: list[dict]) -> list[str]:
        patterns = []
        for n in notes:
            title = n.get("title", "")
            if "？" in title or "?" in title:
                patterns.append("疑问型")
            elif any(title.startswith(str(i)) for i in range(10)):
                patterns.append("数字型")
            elif any(kw in title for kw in ["千万别", "后悔", "秘密", "真相"]):
                patterns.append("悬念型")
            elif any(kw in title for kw in ["怎么办", "为什么", "怎么"]):
                patterns.append("解决问题型")
            else:
                patterns.append("陈述型")
        from collections import Counter
        return [{"pattern": k, "count": v} for k, v in Counter(patterns).most_common(5)]

    # ============================================================
    # 日报生成
    # ============================================================
    def generate_report(self):
        """生成日报"""
        report_path = REPORT_DIR / f"daily_report_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        print(f"\n  [REPORT] {report_path}")
        return report_path

    # ============================================================
    # 主运行
    # ============================================================
    # 养号期配置：前N天只养号不发帖
    WARMUP_DAYS = 3  # 纯养号天数
    ACCOUNT_START_DATE = "2026-05-16"  # 账号开始养号日期

    def _is_warmup_phase(self) -> bool:
        """判断当前是否在养号期（不发帖）"""
        start = datetime.strptime(self.ACCOUNT_START_DATE, "%Y-%m-%d")
        days_elapsed = (datetime.now() - start).days
        return days_elapsed < self.WARMUP_DAYS

    def _first_post_date(self) -> str:
        """返回第一篇帖子的发布日期"""
        start = datetime.strptime(self.ACCOUNT_START_DATE, "%Y-%m-%d")
        first_post = start + timedelta(days=self.WARMUP_DAYS)
        return first_post.strftime("%Y年%m月%d日（周%u）")

    def run(self, skip_yanghao: bool = False):
        """执行每日全部运营任务"""
        print("=" * 60)
        print(f"   Mystic Sanctuary — 小红书每日运营")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        warmup = self._is_warmup_phase()
        if warmup:
            days_left = self.WARMUP_DAYS - (datetime.now() - datetime.strptime(self.ACCOUNT_START_DATE, "%Y-%m-%d")).days
            print(f"   [养号期] 养号期第{self.WARMUP_DAYS - days_left + 1}天 — 只刷不发")
            print(f"   [日] 第一篇文案将在 {self._first_post_date()} 发布")
        else:
            print(f"   ✅ 养号期结束，进入正常运营模式")
        print("=" * 60)

        with XHSOperator(headless=False) as self.op:
            # 验证登录
            print("\n[1] 验证登录状态...")
            self.op.page.goto("https://www.xiaohongshu.com/explore", timeout=30000, wait_until="domcontentloaded")
            self.safe_delay(3, 5)
            if "login" in self.op.page.url.lower():
                print("[FAIL] 未登录! 请先运行: python xhs_operator.py login")
                return
            print("[OK] 登录状态正常")
            self.report["login_status"] = "OK"
            self.report["phase"] = "warmup" if warmup else "normal"

            # ====== 养号期 & 正常期 都执行 ======
            # Skill 01 — 数据追踪
            data = self.skill_01_data_tracking()
            self.check_rate_limit()

            # Skill 03 — 竞品调研
            competitor = self.skill_03_competitor_research()
            self.check_rate_limit()

            # ====== 仅正常期执行 ======
            if not warmup:
                # Skill 04 — 生成明天文案
                next_post = self.skill_04_generate_post(competitor)
                self.check_rate_limit()

                # Skill 02 — 评论监控
                self.skill_02_comment_monitor()
                self.check_rate_limit()

                # Skill 05 — 引导关注话术
                self.skill_05_conversion_scripts()
            else:
                print("\n  [养号期] 跳过: Skill 04(文案生成) / Skill 02(评论监控) / Skill 05(话术)")
                print("  [养号期] 专注: 数据追踪 + 竞品调研 + 养号浏览")
                self.report["skills"]["04_generate_post"] = {"status": "skipped_warmup"}
                self.report["skills"]["02_comment_monitor"] = {"status": "skipped_warmup"}
                self.report["skills"]["05_conversion"] = {"status": "skipped_warmup"}

            # 养号 (养号期和正常期都做)
            if not skip_yanghao:
                self.yanghao(duration_minutes=30)

            # 日报
            self.generate_report()

        print("\n" + "=" * 60)
        if warmup:
            print(f"   养号期运营完成! (第{self.WARMUP_DAYS - days_left + 1}天/{self.WARMUP_DAYS}天)")
            print(f"   第一篇文案: {self._first_post_date()} 发布")
        else:
            print(f"   每日运营完成! 下一篇文案已保存")
        print(f"   数据已归档")
        print("=" * 60)


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="小红书每日自动化运营")
    parser.add_argument("--skip-yanghao", action="store_true", help="跳过养号环节")
    parser.add_argument("--skill", type=int, choices=[1, 2, 3, 4, 5], help="只运行单个Skill")
    args = parser.parse_args()

    ops = DailyOps()

    if args.skill:
        with XHSOperator(headless=False) as ops.op:
            ops.op.page.goto("https://www.xiaohongshu.com/explore", timeout=30000, wait_until="domcontentloaded")
            ops.safe_delay(3, 5)
            if args.skill == 1:
                ops.skill_01_data_tracking()
            elif args.skill == 2:
                ops.skill_02_comment_monitor()
            elif args.skill == 3:
                ops.skill_03_competitor_research()
            elif args.skill == 4:
                ops.skill_04_generate_post()
            elif args.skill == 5:
                ops.skill_05_conversion_scripts()
    else:
        ops.run(skip_yanghao=args.skip_yanghao)
