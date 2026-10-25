#!/usr/bin/env python3
"""Export every built demo to demos-index.csv and demos-index.md.

Prefer Turso (leads.demo_token + demo_sites.token). Without credentials,
rebuild from public Daily lead pipeline logs and optional enrichment tables.

Usage:
  python3 scripts/export_demos_index.py
  python3 scripts/export_demos_index.py --logs /tmp/pipeline-logs --enrich docs/menu_sources.md
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROD_HOST = "https://restaurant-ai-bot-two.vercel.app"
# Confirmed in server.py, pipeline.py, bot.py, ops.py: /demo/<token>
DEMO_PATH = "/demo/"
CSV_COLS = ["name", "demo_url", "city", "category", "website_status", "token", "lead_id"]


def demo_url(token: str) -> str:
    return f"{PROD_HOST}{DEMO_PATH}{token}"


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def rows_from_turso() -> tuple[list[dict], str]:
    try:
        import db
    except ImportError:
        return [], "turso_unconfigured"

    if not db.turso_configured():
        return [], "turso_unconfigured"
    db.ensure_schema()
    seen: dict[str, dict] = {}
    with db.conn() as c:
        lead_rows = c.execute(
            "SELECT id, name, city, category, website_status, demo_token "
            "FROM leads WHERE demo_token IS NOT NULL AND demo_token != ''"
        ).fetchall()
        site_rows = c.execute(
            "SELECT demo_sites.token, demo_sites.lead_id, "
            "leads.name, leads.city, leads.category, leads.website_status "
            "FROM demo_sites LEFT JOIN leads ON leads.id = demo_sites.lead_id"
        ).fetchall()
    for r in lead_rows:
        token = _cell(r["demo_token"])
        if not token:
            continue
        seen[token] = {
            "name": _cell(r["name"]),
            "demo_url": demo_url(token),
            "city": _cell(r["city"]),
            "category": _cell(r["category"]),
            "website_status": _cell(r["website_status"]),
            "token": token,
            "lead_id": _cell(r["id"]),
        }
    for r in site_rows:
        token = _cell(r["token"])
        if not token:
            continue
        existing = seen.get(token)
        if existing:
            if not existing["lead_id"] and r["lead_id"] is not None:
                existing["lead_id"] = _cell(r["lead_id"])
            continue
        seen[token] = {
            "name": _cell(r["name"]),
            "demo_url": demo_url(token),
            "city": _cell(r["city"]),
            "category": _cell(r["category"]),
            "website_status": _cell(r["website_status"]),
            "token": token,
            "lead_id": _cell(r["lead_id"]),
        }
    return list(seen.values()), "turso"


def rows_from_pipeline_logs(log_dir: Path) -> list[dict]:
    seen: dict[str, dict] = {}
    if not log_dir.is_dir():
        return []
    for path in sorted(log_dir.glob("*.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"sites_generated"' not in line:
                continue
            start = line.find("{")
            if start < 0:
                continue
            try:
                payload = json.loads(line[start:])
            except json.JSONDecodeError:
                continue
            for site in payload.get("sites") or []:
                token = _cell(site.get("token"))
                if not token:
                    continue
                seen[token] = {
                    "name": _cell(site.get("name")),
                    "demo_url": demo_url(token),
                    "city": "",
                    "category": "",
                    "website_status": "",
                    "token": token,
                    "lead_id": _cell(site.get("lead")),
                }
    return list(seen.values())


_MD_ROW = re.compile(
    r"^\| (?!name )(?P<name>[^|]+?) \| (?P<city>[^|]*) \| (?P<category>[^|]*) \| "
    r"https://restaurant-ai-bot-two\.vercel\.app/demo/(?P<token>[^| \t]+) \|"
)


def enrich_from_markdown(rows: list[dict], md_path: Path) -> list[dict]:
    if not md_path.is_file():
        return rows
    by_token = {r["token"]: r for r in rows}
    for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _MD_ROW.match(line.strip())
        if not m:
            continue
        token = m.group("token").strip()
        name = m.group("name").strip()
        city = m.group("city").strip()
        category = m.group("category").strip()
        row = by_token.get(token)
        if row is None:
            row = {
                "name": name,
                "demo_url": demo_url(token),
                "city": city,
                "category": category,
                "website_status": "",
                "token": token,
                "lead_id": "",
            }
            by_token[token] = row
            continue
        if name and not row["name"]:
            row["name"] = name
        if city and not row["city"]:
            row["city"] = city
        if category and not row["category"]:
            row["category"] = category
    return list(by_token.values())


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: ((r.get("name") or "").lower(), r.get("token") or ""))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_COLS})


def write_md(path: Path, rows: list[dict], source: str, production_demos: int | None) -> None:
    lines = [
        "# Demo index",
        "",
        f"Public URL pattern: `{PROD_HOST}/demo/{{token}}` "
        "(from `server.py` `/demo/<token>`, also `pipeline.py` / `bot.py` / `ops.py`).",
        "",
        f"Rows in this file: **{len(rows)}**",
    ]
    if production_demos is not None:
        lines.append(
            f"Production `/stats` funnel.demos (leads with a token): **{production_demos}**"
        )
    if source == "turso":
        lines.append("Source: Turso `leads.demo_token` + `demo_sites.token`.")
    else:
        lines.append(
            "Source: public GitHub Actions Daily lead pipeline logs "
            "(each `/pipeline/run` JSON `sites[]` record) plus city/category "
            "enrichment from known live `/demo/<token>` pages documented in PR 18. "
            "Turso credentials were not available in this environment, and "
            "`demos/*.html` is gitignored, so this is not the full production set."
        )
    lines += [
        "",
        "| name | demo_url |",
        "| --- | --- |",
    ]
    for row in rows:
        name = (row.get("name") or "").replace("|", "\\|")
        lines.append(f"| {name} | {row['demo_url']} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def fetch_production_demo_count() -> int | None:
    import urllib.request

    try:
        with urllib.request.urlopen(f"{PROD_HOST}/stats", timeout=20) as resp:
            payload = json.loads(resp.read().decode())
        return int((payload.get("funnel") or {}).get("demos"))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "demos-index.csv")
    parser.add_argument("--md", type=Path, default=ROOT / "demos-index.md")
    parser.add_argument("--logs", type=Path, default=Path("/tmp/pipeline-logs"))
    parser.add_argument(
        "--enrich",
        type=Path,
        default=ROOT / "docs" / "menu_sources.md",
        help="Optional markdown table with name/city/category/token columns",
    )
    args = parser.parse_args()

    rows, source = rows_from_turso()
    if not rows:
        rows = rows_from_pipeline_logs(args.logs)
        source = "pipeline_logs" if rows else source
        rows = enrich_from_markdown(rows, args.enrich)
    if not rows:
        seed_path = ROOT / "scripts" / "demo_index_seed.json"
        if seed_path.is_file():
            rows = json.loads(seed_path.read_text(encoding="utf-8"))
            source = "seed"

    rows = sort_rows(rows)
    if not rows:
        print(
            "No demos found. Set TURSO_DATABASE_URL + TURSO_AUTH_TOKEN, "
            "or pass --logs with Daily pipeline run logs.",
            file=sys.stderr,
        )
        return 1

    write_csv(args.csv, rows)
    write_md(args.md, rows, source, fetch_production_demo_count())
    print(f"wrote {len(rows)} demos from {source}")
    print(f"  {args.csv}")
    print(f"  {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
