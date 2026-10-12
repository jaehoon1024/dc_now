#!/usr/bin/env python3
"""Build the public dashboard and publish changed static data to GitHub Pages."""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLISH_PATHS = (
    "deploy/index.html",
    "deploy/data.json",
    "deploy/manager.js",
    "deploy/manager-core.js",
    "deploy/manager.css",
    "deploy/.nojekyll",
    "deploy/_headers",
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
        timeout=180,
    )


def main() -> int:
    run(str(ROOT / ".venv/bin/python"), str(ROOT / "src21_build_static_site.py"))
    changed = run("git", "status", "--porcelain", "--", *PUBLISH_PATHS).stdout.strip()
    if not changed:
        print("대시보드 변경 없음")
        return 0
    run("git", "add", "--", *PUBLISH_PATHS)
    message = f"Update dashboard data {datetime.now().astimezone():%Y-%m-%d}"
    run("git", "commit", "--only", "-m", message, "--", *PUBLISH_PATHS)
    run("git", "push", "origin", "main")
    print("대시보드 데이터 게시 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
