#!/usr/bin/env python3
"""Import the Sep-7 contractor outreach list into leads, and build their demos.

Those 21 businesses were emailed once from outside the bot, so the database
never knew about them: no lead rows, no demo sites, and the "preview" link in
that email pointed at a generic landing page rather than their own site.

This puts them in the system properly so the normal pipeline can work them —
which also means unsubscribe links and the postal address get attached, which
the original send lacked.

    python3 scripts/import_contractors.py /tmp/contractors.json         # preview
    python3 scripts/import_contractors.py /tmp/contractors.json --apply
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config as C  # noqa: E402
import db  # noqa: E402
from generator import generate_site  # noqa: E402

# Subject lines truncated long names; restore the ones we can read.
NAME_FIXES = {
    "Coastal Backflow Prevention Servic": "Coastal Backflow Prevention Services",
    "American Certification Inc. DBA Ce": "American Certification Inc.",
    "Texas Backflow Testing & Repairs,": "Texas Backflow Testing & Repairs",
    "TP Backflow Testing Inc. / Tan Pha": "TP Backflow Testing Inc.",
    "Intensity Electrical Contractors L": "Intensity Electrical Contractors LLC",
}

# Category by what the business actually does, so the generated site uses the
# right template, hero, and sections.
RULES = [
    (r"backflow|plumb|testing", "plumber"),
    (r"electric", "electrician"),
    (r"cake|oven|bakery|baker", "bakery"),
    (r"barber", "barber"),
    (r"salon|hair|beauty", "salon"),
    (r"kitchen|chamoy|fried|taste|affair", "restaurant"),
    (r"evap|hvac|air", "hvac"),
    (r"roof", "roofer"),
    (r"lawn|landscap", "lawn"),
    (r"pool", "pool"),
]


def categorize(name: str) -> str:
    low = name.lower()
    for pattern, cat in RULES:
        if re.search(pattern, low):
            return cat
    return "plumber"  # this list is overwhelmingly trades


def clean(name: str) -> str:
    return NAME_FIXES.get(name, name).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", help="JSON list of {name, email, city}")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--city", default="houston", help="fallback city")
    a = p.parse_args()

    rows = json.loads(Path(a.path).read_text())
    with db.conn() as c:
        known = {r[0] for r in c.execute(
            "SELECT email FROM leads WHERE email IS NOT NULL AND email <> ''")}

    made = skipped = 0
    for r in rows:
        name = clean(r["name"])
        email = r["email"]
        cat = categorize(name)
        city = (r.get("city") or "").strip().lower()
        if city not in C.CITIES:
            city = a.city
        if email in known:
            print(f"skip   {name[:36]:36} {email}  (already a lead)")
            skipped += 1
            continue
        print(f"{'import' if a.apply else 'would':6} {name[:36]:36} {cat:11} {city:8} {email}")
        if not a.apply:
            continue

        biz_id = db.upsert_business(
            name=name, phone="", address="", city=city, area="",
            category=cat, rating=0, website="", website_status="none")
        if not biz_id:
            print(f"       ! upsert_business returned nothing for {name}")
            continue
        lead_id = db.create_lead(
            biz_id, name=name, phone="", email=email, address="", city=city,
            area="", category=cat, rating=0, website_status="none",
            notes="source: Sep-7 contractor outreach list (emailed once "
                  "outside the bot, no demo link)")
        # fetch_place=False: no address/phone to match on, and the Google
        # budget is shared with the other agent.
        html_str, token = generate_site(
            name=name, address="", phone="", category=cat, rating=0,
            city=city, lead_id=lead_id, business_id=biz_id, fetch_place=False)
        db.create_demo_site(lead_id, biz_id, html_str, token, template_used=cat)
        db.update_lead(
            lead_id, status="site_generated", demo_token=token,
            demo_created_at=datetime.now().isoformat(),
            demo_expires_at=(datetime.now()
                             + timedelta(hours=C.DEMO_EXPIRE_HOURS)).isoformat())
        print(f"       -> lead {lead_id}  demo /demo/{token}")
        made += 1

    print(f"\n{'imported' if a.apply else 'would import'}: {made}, skipped: {skipped}")


if __name__ == "__main__":
    main()
