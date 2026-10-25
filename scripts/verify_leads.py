#!/usr/bin/env python3
"""Classify every unverified lead via Google Places, so the pipeline can pitch.

The send stage refuses any lead whose website status it cannot confirm, and
that check is one Google call per business. Rationed at 50/day it would take
11+ days; this clears the backlog in one paid pass (~$0.032/call).

Marks has_site leads dead — they already have a website and must never be
told otherwise. That mistake reached 4 real businesses on 2026-09-07.

    GOOGLE_PLACES_DAILY_BUDGET=700 python3 scripts/verify_leads.py --limit 50
    GOOGLE_PLACES_DAILY_BUDGET=700 python3 scripts/verify_leads.py --all --apply
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from scanner.scanner import google_enrich  # noqa: E402


def candidates(limit: int):
    with db.conn() as c:
        rows = c.execute(
            "SELECT id, business_id, name, address, city FROM leads "
            "WHERE website_status IN ('none','unknown') "
            "AND status NOT IN ('dead','sold') "
            # Leads with an address match far more reliably; do them first so
            # a partial run still produces the most usable result.
            "ORDER BY (address IS NOT NULL AND address != '') DESC, id "
            "LIMIT ?", (limit,)).fetchall()
    return [(r[0], r[1], r[2], r[3] or "", r[4] or "") for r in rows]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--all", action="store_true", help="every unverified lead")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--sleep", type=float, default=0.4, help="pause between calls")
    a = p.parse_args()

    leads = candidates(100000 if a.all else a.limit)
    print(f"{len(leads)} leads to classify"
          f"{'' if a.apply else '  (DRY RUN — no writes, but calls still cost)'}")
    print(f"est. cost ${len(leads) * 0.032:.2f}\n")

    tally = {"none": 0, "social_only": 0, "has_site": 0, "no_match": 0, "error": 0}
    for i, (lead_id, biz_id, name, address, city) in enumerate(leads, 1):
        # Google matches far better with a city qualifier than a bare street.
        query_addr = address or f"{city.title()}, TX" if city else address
        try:
            info = google_enrich(name, query_addr)
        except Exception as exc:
            tally["error"] += 1
            print(f"  [{i}/{len(leads)}] {name[:30]:30} ERROR {exc}")
            continue
        if not info:
            tally["no_match"] += 1
        else:
            status = info.get("website_status") or "unknown"
            tally[status] = tally.get(status, 0) + 1
            if a.apply:
                fields = {"website_status": status}
                # Always keep the phone: the same paid response carries it,
                # and discarding it for address-having leads threw away 541
                # numbers we had already paid for.
                if info.get("phone"):
                    fields["phone"] = info["phone"]
                if status == "has_site":
                    fields["status"] = "dead"
                db.update_lead(lead_id, **fields)
            if status == "has_site":
                print(f"  [{i}/{len(leads)}] {name[:30]:30} HAS SITE -> dead")
        if i % 25 == 0:
            print(f"  ... {i}/{len(leads)}  {tally}")
        time.sleep(a.sleep)

    print("\nresult:", tally)
    pitchable = tally["none"] + tally["social_only"]
    print(f"pitchable (none/social_only): {pitchable}")
    print(f"already had a site          : {tally['has_site']}")
    print(f"unmatchable                 : {tally['no_match']}")


if __name__ == "__main__":
    main()
