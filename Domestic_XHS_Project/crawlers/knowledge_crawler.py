#!/usr/bin/env python3
"""知识爬虫 — 爬取道家命理古籍 + Z-Library + 希腊神话 + 心理学

目标网站:
- 道家书籍网 (daojiashuji.com) — 道门典籍、命理书籍
- Z-Library — 中国道教文化、命理学、西方命理、希腊神话、量子力学、心理学
- 中国哲学书电子化计划 (ctext.org) — 正统道藏
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from datetime import datetime

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

# 知识分类目录映射
CATEGORIES = {
    "道藏": "knowledge/中华图书网/道藏",
    "命理": "knowledge/中华图书网/命理",
    "风水": "knowledge/中华图书网/风水",
    "丹道": "knowledge/中华图书网/丹道",
    "符咒": "knowledge/中华图书网/符咒",
    "西方命理": "knowledge/zlibrary/西方命理",
    "希腊神话": "knowledge/希腊神话",
    "量子力学": "knowledge/量子力学",
    "心理学": "knowledge/心理学",
}


def ensure_dirs():
    for d in CATEGORIES.values():
        (KNOWLEDGE_DIR.parent / d).mkdir(parents=True, exist_ok=True)


def fetch_url(url: str, timeout: int = 30) -> str | None:
    """安全地获取网页内容"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [ERR] {url[:60]}: {e}")
        return None


def crawl_daojiashuji() -> list[dict]:
    """爬取道家书籍网 (daojiashuji.com) 的命理和道藏书籍目录"""
    print("\n=== 爬取 道家书籍网 ===")
    results = []
    urls = [
        "https://www.daojiashuji.com/mingli/",  # 命理
        "https://www.daojiashuji.com/fengshui/",  # 风水
        "https://www.daojiashuji.com/daojia/",  # 道家
    ]

    for url in urls:
        print(f"  [*] {url}")
        html = fetch_url(url)
        if not html:
            continue

        # 提取书籍链接和标题
        titles = re.findall(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"', html)
        for link, title in titles:
            if any(kw in title.lower() for kw in ["命", "运", "卦", "易", "道", "风", "水", "符", "咒", "丹"]):
                results.append({
                    "title": title.strip(),
                    "url": link if link.startswith("http") else url.rstrip("/") + "/" + link.lstrip("/"),
                    "source": "道家书籍网",
                    "category": classify_category(title),
                })
        print(f"    Found {len(titles)} links")

    return results


def crawl_ctext() -> list[dict]:
    """爬取中国哲学书电子化计划 (ctext.org) 的道藏相关典籍"""
    print("\n=== 爬取 ctext.org (正统道藏) ===")
    results = []
    # ctext.org 道藏目录
    urls = [
        "https://ctext.org/daoism/zh",
        "https://ctext.org/library.pl?if=gb&res=84327",
    ]

    for url in urls:
        print(f"  [*] {url}")
        html = fetch_url(url)
        if not html:
            continue

        # 提取书籍信息
        items = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html)
        for link, title in items:
            title = title.strip()
            if len(title) > 3 and not title.startswith("<"):
                results.append({
                    "title": title,
                    "url": f"https://ctext.org{link}" if link.startswith("/") else link,
                    "source": "ctext.org",
                    "category": classify_category(title),
                })

    print(f"    Found {len(results)} items")
    return results


def crawl_daozang_index() -> list[dict]:
    """爬取道家经典索引 — 收录主要道藏目录和简介"""
    print("\n=== 构建道家经典索引 ===")
    # 道藏核心典籍列表(手动维护经典书目)
    classics = [
        {"title": "道德经", "author": "老子", "category": "道藏", "era": "春秋"},
        {"title": "庄子", "author": "庄周", "category": "道藏", "era": "战国"},
        {"title": "列子", "author": "列御寇", "category": "道藏", "era": "战国"},
        {"title": "周易参同契", "author": "魏伯阳", "category": "丹道", "era": "东汉"},
        {"title": "黄庭经", "author": "佚名", "category": "丹道", "era": "晋"},
        {"title": "抱朴子", "author": "葛洪", "category": "丹道", "era": "东晋"},
        {"title": "太上感应篇", "author": "佚名", "category": "道藏", "era": "宋"},
        {"title": "文昌帝君阴骘文", "author": "佚名", "category": "道藏", "era": "宋"},
        {"title": "性命圭旨", "author": "尹真人", "category": "丹道", "era": "明"},
        {"title": "太乙金华宗旨", "author": "吕洞宾", "category": "丹道", "era": "清"},
        {"title": "道藏辑要", "author": "彭定求 编", "category": "道藏", "era": "清"},
        {"title": "云笈七签", "author": "张君房", "category": "道藏", "era": "宋"},
        {"title": "悟真篇", "author": "张伯端", "category": "丹道", "era": "宋"},
        {"title": "黄帝阴符经", "author": "佚名", "category": "道藏", "era": "先秦"},
        {"title": "清静经", "author": "佚名", "category": "道藏", "era": "唐"},
        {"title": "三命通会", "author": "万民英", "category": "命理", "era": "明"},
        {"title": "渊海子平", "author": "徐子平", "category": "命理", "era": "宋"},
        {"title": "滴天髓", "author": "刘伯温", "category": "命理", "era": "明"},
        {"title": "穷通宝鉴", "author": "余春台", "category": "命理", "era": "清"},
        {"title": "子平真诠", "author": "沈孝瞻", "category": "命理", "era": "清"},
        {"title": "神峰通考", "author": "张神峰", "category": "命理", "era": "明"},
        {"title": "卜筮正宗", "author": "王洪绪", "category": "命理", "era": "清"},
        {"title": "增删卜易", "author": "野鹤老人", "category": "命理", "era": "清"},
        {"title": "梅花易数", "author": "邵雍", "category": "命理", "era": "宋"},
        {"title": "皇极经世", "author": "邵雍", "category": "命理", "era": "宋"},
        {"title": "葬书", "author": "郭璞", "category": "风水", "era": "晋"},
        {"title": "撼龙经", "author": "杨筠松", "category": "风水", "era": "唐"},
        {"title": "宅经", "author": "佚名", "category": "风水", "era": "唐"},
        {"title": "地理五诀", "author": "赵九峰", "category": "风水", "era": "清"},
        {"title": "阳宅三要", "author": "赵九峰", "category": "风水", "era": "清"},
        {"title": "鲁班经", "author": "佚名", "category": "风水", "era": "明"},
        {"title": "太上老君说常清静经", "author": "佚名", "category": "道藏", "era": "先秦"},
        {"title": "度人经", "author": "佚名", "category": "道藏", "era": "魏晋"},
        {"title": "玉皇经", "author": "佚名", "category": "道藏", "era": "宋"},
        {"title": "北斗经", "author": "佚名", "category": "道藏", "era": "唐"},
        {"title": "三官经", "author": "佚名", "category": "道藏", "era": "南北朝"},
        {"title": "道德真經廣聖義", "author": "杜光庭", "category": "道藏", "era": "唐"},
    ]
    print(f"  [OK] {len(classics)} classic texts indexed")
    return classics


def classify_category(title: str) -> str:
    """根据标题自动分类"""
    title_lower = title
    if any(kw in title_lower for kw in ["命", "运", "卦", "易", "卜", "八字", "子平"]):
        return "命理"
    elif any(kw in title_lower for kw in ["风", "水", "宅", "葬", "地理", "龙"]):
        return "风水"
    elif any(kw in title_lower for kw in ["丹", "金丹", "内丹", "修炼"]):
        return "丹道"
    elif any(kw in title_lower for kw in ["符", "咒", "箓", "法", "术"]):
        return "符咒"
    else:
        return "道藏"


def save_knowledge(data: list[dict], filename: str, category: str = "道藏"):
    """保存知识到文件"""
    dir_path = KNOWLEDGE_DIR / "中华图书网" / category if category in ["道藏", "命理", "风水", "丹道", "符咒"] else KNOWLEDGE_DIR.parent / CATEGORIES.get(category, "knowledge")
    dir_path = Path(str(dir_path).replace("knowledge/knowledge/", "knowledge/"))
    dir_path.mkdir(parents=True, exist_ok=True)

    path = dir_path / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "crawled_at": datetime.now().isoformat(),
            "source": filename.replace(".json", ""),
            "count": len(data),
            "items": data,
        }, f, indent=2, ensure_ascii=False)
    print(f"  [SAVED] {path} ({len(data)} items)")


def main():
    print(f"{'='*50}")
    print(f"Metaphysics Knowledge Crawler")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    ensure_dirs()

    # 1. 道家书籍网
    try:
        books = crawl_daojiashuji()
        if books:
            save_knowledge(books, "daojiashuji_books.json", "道藏")
    except Exception as e:
        print(f"  [SKIP] 道家书籍网: {e}")

    # 2. ctext.org 道藏
    try:
        ctext_items = crawl_ctext()
        if ctext_items:
            save_knowledge(ctext_items, "ctext_daoist.json", "道藏")
    except Exception as e:
        print(f"  [SKIP] ctext: {e}")

    # 3. 道藏经典索引
    try:
        classics = crawl_daozang_index()
        save_knowledge(classics, "daozang_classics.json", "道藏")
    except Exception as e:
        print(f"  [SKIP] daozang: {e}")

    print(f"\n{'='*50}")
    print(f"Knowledge crawl complete.")
    print(f"Directory: {KNOWLEDGE_DIR}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
