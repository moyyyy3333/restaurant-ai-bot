#!/usr/bin/env python3
"""Run every pipeline stage without sending outreach."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
from pipeline import run_daily  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scan-budget",
        type=int,
        default=int(os.getenv("PIPELINE_SCAN_BUDGET", "0")),
        help="LocationIQ areas to scan (0 is safe for local checks)",
    )
    args = parser.parse_args()
    db.init_db()
    report = run_daily(send_limit=0, scan_budget=max(0, args.scan_budget))
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
