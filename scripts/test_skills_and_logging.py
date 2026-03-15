#!/usr/bin/env python3
# File: test_skills_and_logging.py
# Description: Test client, server tool, and Watson-style logging.
# Created: 2026-03-15
# Last updated: 2026-03-15

"""
Run from repo root with .env set:
  cd ultrahuman-mcp && source .env 2>/dev/null || true
  .venv/bin/python scripts/test_skills_and_logging.py
Or: ULTRAHUMAN_LOG_JSON=1 .venv/bin/python scripts/test_skills_and_logging.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Repo root and load .env
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
try:
    env_file = _root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
except Exception:
    pass
sys.path.insert(0, str(_root))

# Configure Watson-style JSON logging for test
from ultrahuman_mcp.log_config import configure_logging
configure_logging(use_json=True)

from ultrahuman_mcp.client import fetch_daily_metrics
from ultrahuman_mcp.server import ultrahuman_get_daily_metrics, _format_daily_metrics_markdown
from ultrahuman_mcp.models import GetDailyMetricsInput


def main():
    email = os.getenv("ULTRAHUMAN_EMAIL", "").strip()
    if not email:
        print("SKIP: ULTRAHUMAN_EMAIL not set (no .env or empty)")
        return 0
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print("=== 1) Client: fetch 1 day ===")
    try:
        data = fetch_daily_metrics(email, yesterday)
        n = len((data.get("data") or {}).get("metric_data") or [])
        print(f"OK – metric_data count: {n}")
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    print("\n=== 2) Client: fetch 3 days (simulate weekly) ===")
    for i in range(1, 4):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            fetch_daily_metrics(email, d)
            print(f"  [{i}/3] {d} OK")
        except Exception as e:
            print(f"  [{i}/3] {d} FAIL: {e}")

    print("\n=== 3) Server tool: ultrahuman_get_daily_metrics ===")
    try:
        params = GetDailyMetricsInput(email=email, date=yesterday, response_format="markdown")
        out = asyncio.run(ultrahuman_get_daily_metrics(params))
        if out.startswith("Error:"):
            print(f"FAIL: {out}")
        else:
            lines = [l for l in out.split("\n") if l.strip()][:8]
            print("OK – output (first 8 lines):")
            for l in lines:
                print(" ", l[:70] + ("..." if len(l) > 70 else ""))
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    print("\n=== 4) Markdown formatter (from raw data) ===")
    try:
        md = _format_daily_metrics_markdown(data)
        print("OK – formatted length:", len(md))
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    print("\n=== All checks passed ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
