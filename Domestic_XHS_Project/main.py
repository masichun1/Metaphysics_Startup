#!/usr/bin/env python3
"""Metaphysics Startup — 国内小红书业务主入口调度器

Usage:
    python main.py run skill_01            # 数据追踪
    python main.py run skill_02            # 评论监控
    python main.py run skill_03 --topic 塔罗  # 竞品调研
    python main.py run skill_04 --niche 塔罗占卜  # 冷启动方案
    python main.py run skill_05 --niche 塔罗占卜  # 引导关注话术
    python main.py run-all                 # 运行全部
    python main.py serve                   # 启动 OpenCLI 交互式调度
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config_loader import load_config
from core.logger import setup_logging, get_logger

logger = logging.getLogger("xhs.main")

# AI client will be lazily initialized
_ai_client = None


def get_ai_client(config):
    """Lazy-load the Anthropic client."""
    global _ai_client
    if _ai_client is None:
        api_key = config.anthropic_api_key or ""
        if not api_key:
            print("Warning: ANTHROPIC_API_KEY not set. AI analysis will be skipped.")
            return None
        try:
            from anthropic import Anthropic
            _ai_client = type(
                "SimpleAIClient", (), {
                    "_client": Anthropic(api_key=api_key),
                    "_model": config.anthropic_model,
                    "generate_text": lambda self, user_prompt, max_tokens=1024: self._client.messages.create(
                        model=self._model,
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": user_prompt}],
                    ).content[0].text,
                }
            )()
        except ImportError:
            print("Warning: anthropic package not installed. AI analysis will be skipped.")
            return None
        except Exception as e:
            print(f"Warning: Failed to init AI client: {e}")
            return None
    return _ai_client


def run_skill(skill_id: str, config, ai_client, **kwargs):
    """Run a single XHS skill."""
    skills_map = {
        "skill_01": ("skills.skill_01_data_tracking.main", "Skill01DataTracking"),
        "skill_02": ("skills.skill_02_comment_monitor.main", "Skill02CommentMonitor"),
        "skill_03": ("skills.skill_03_competitor_research.main", "Skill03CompetitorResearch"),
        "skill_04": ("skills.skill_04_cold_start.main", "Skill04ColdStart"),
        "skill_05": ("skills.skill_05_follow_conversion.main", "Skill05FollowConversion"),
    }

    if skill_id not in skills_map:
        available = ", ".join(skills_map.keys())
        print(f"Unknown skill '{skill_id}'. Available: {available}")
        sys.exit(1)

    module_path, class_name = skills_map[skill_id]
    import importlib
    module = importlib.import_module(module_path)
    skill_class = getattr(module, class_name)
    skill = skill_class(ai_client=ai_client, config=config)

    result = skill.run(**kwargs)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Metaphysics XHS (小红书) Automation Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run skill_01
  python main.py run skill_03 --topic 塔罗占卜
  python main.py run skill_04 --niche "星座情感" --days 14
  python main.py run-all
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_parser = sub.add_parser("run", help="Run a single skill")
    run_parser.add_argument("skill", help="Skill ID (skill_01 through skill_05)")
    run_parser.add_argument("--topic", default="塔罗", help="Topic for research (skill_03)")
    run_parser.add_argument("--niche", default="塔罗占卜", help="Niche for planning (skill_04/05)")
    run_parser.add_argument("--days", type=int, default=30, help="Planning days (skill_04)")
    run_parser.add_argument("--keywords", nargs="+", help="Keywords to track (skill_01)")
    run_parser.add_argument("--accounts", nargs="+", help="Accounts to monitor (skill_01)")
    run_parser.add_argument("--note-title", default="", help="Note title for comment analysis (skill_02)")

    # --- run-all ---
    sub.add_parser("run-all", help="Run all XHS skills sequentially")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Load config
    load_dotenv()
    config = load_config()
    setup_logging(level=config.log_level)

    ai_client = get_ai_client(config)

    if args.command == "run":
        kwargs = {}
        for key in ["topic", "niche", "days", "keywords", "accounts", "note_title"]:
            if hasattr(args, key):
                val = getattr(args, key)
                if val is not None:
                    kwargs[key] = val

        result = run_skill(args.skill, config, ai_client, **kwargs)

        print(f"\n{'='*50}")
        print(f"Skill: {args.skill}")
        print(f"Generated at: {result.get('generated_at', 'N/A')}")
        # Show key stats
        for key in result:
            if key.endswith("_count") or key.endswith("_analyzed") or key.endswith("_collected"):
                print(f"  {key}: {result[key]}")
        if "claude_strategy" in result:
            print(f"\n[Claude 策略分析]")
            print(result["claude_strategy"][:500])
            if len(result.get("claude_strategy", "")) > 500:
                print("... (内容已截断，完整内容请查看导出文件)")
        if "safety_guidelines" in result:
            print(f"\n[安全执行规范] ({len(result['safety_guidelines'])} 条)")
        print(f"\nExport directory: data/exports/")
        print(f"{'='*50}\n")

    elif args.command == "run-all":
        all_skills = ["skill_01", "skill_02", "skill_03", "skill_04", "skill_05"]
        for sid in all_skills:
            print(f"\n>>> Running {sid}...")
            try:
                result = run_skill(sid, config, ai_client)
                print(f"    Complete: {result.get('generated_at', 'N/A')}")
            except Exception as e:
                print(f"    FAILED: {e}")


if __name__ == "__main__":
    main()
