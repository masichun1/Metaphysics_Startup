#!/usr/bin/env python3
"""每日自动 Git 存档 — 运营数据 + 代码变更

在每日养号+运营完成后执行 (约 6:00 AM)
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_git(cmd: list[str]) -> str:
    """Run git command in repo root, return output"""
    result = subprocess.run(
        ["git"] + cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout + result.stderr


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today}] 每日 Git 自动存档")

    # Stage all changes
    out = run_git(["add", "-A"])
    print(f"  git add: {out.strip()[:200]}")

    # Check if there are changes to commit
    status = run_git(["status", "--porcelain"])
    if not status.strip():
        print("  No changes to commit.")
        return

    # Commit
    commit_msg = f"每日自动存档: {today} 小红书运营数据"
    out = run_git(["commit", "-m", commit_msg])
    print(f"  git commit: {out.strip()[:200]}")

    # Push
    out = run_git(["push", "origin", "master"])
    print(f"  git push: {out.strip()[:200]}")

    print(f"[{today}] 存档完成")


if __name__ == "__main__":
    main()
