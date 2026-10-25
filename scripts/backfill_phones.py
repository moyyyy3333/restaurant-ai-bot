#!/usr/bin/env python3
"""Fill missing lead phone numbers from OpenStreetMap — free, no API budget.

327 leads discovered by the LocationIQ scanner have no phone. Google has them
but charges per lookup; OSM carries phone/contact:phone tags for a good share
of the same businesses and costs nothing.

Matches on normalised name within the lead's city, and only ever fills an
empty phone — never overwrites.

    python3 scripts/backfill_phones.py miami
    python3 scripts/backfill_phones.py miami --apply
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config as C  # noqa: E402
import db  # noqa: E402

OVERPASS = "https://overpass-api.de/api/interpreter"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch_phones(city_key: str) -> dict:
    """Every named POI in the city that publishes a phone number."""
    city = C.CITIES[city_key]
    lat, lng, pad = city["lat"], city["lng"], 0.16
    s, w, n, e = lat - pad, lng - pad * 1.25, lat + pad, lng + pad * 1.25
    q = (f'[out:json][timeout:180];(nwr["name"]["phone"]({s},{w},{n},{e});'
         f'nwr["name"]["contact:phone"]({s},{w},{n},{e}););out tags center;')
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
        headers={"User-Agent": "local-business-phone-backfill/1.0"})
    with urllib.request.urlopen(req, timeout=240) as r:
        els = json.load(r).get("elements", [])
    out = {}
    for el in els:
        t = el.get("tags", {})
        name, phone = t.get("name"), t.get("phone") or t.get("contact:phone")
        if name and phone:
            out.setdefault(norm(name), phone.strip())
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("city")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()

    if a.city not in C.CITIES:
        sys.exit(f"unknown city; known: {', '.join(C.CITIES)}")

    phones = fetch_phones(a.city)
    print(f"{len(phones)} OSM businesses with a phone in {a.city}")

    with db.conn() as c:
        rows = c.execute(
            "SELECT id, business_id, name FROM leads WHERE city = ? "
            "AND (phone IS NULL OR phone = '') "
            "AND status NOT IN ('dead','sold')", (a.city,)).fetchall()
    leads = [(r[0], r[1], r[2]) for r in rows]
    print(f"{len(leads)} leads missing a phone\n")

    hits = 0
    for lead_id, biz_id, name in leads:
        phone = phones.get(norm(name))
        if not phone:
            continue
        hits += 1
        print(f"  {name[:36]:36} {phone}")
        if a.apply:
            # Re-read: never clobber a number added since we listed.
            with db.conn() as c:
                cur = c.execute("SELECT phone FROM leads WHERE id=?", (lead_id,)).fetchone()
            if cur and (cur[0] or "").strip():
                continue
            db.update_lead(lead_id, phone=phone)
            if biz_id:
                with db.conn() as c:
                    c.execute("UPDATE businesses SET phone=? WHERE id=? "
                              "AND (phone IS NULL OR phone='')", (phone, biz_id))
    print(f"\nmatched {hits}/{len(leads)}"
          f"{' (written)' if a.apply else ' (dry run)'}")


if __name__ == "__main__":
    main()
