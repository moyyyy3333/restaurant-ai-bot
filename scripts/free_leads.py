#!/usr/bin/env python3
"""Find local businesses with a phone and NO website, free, from OpenStreetMap.

This is the same data LocationIQ resells, queried directly through Overpass:
no API key, no account, no daily budget. That matters because the paid
counters (LocationIQ 30/day, Google Places 50/day) are shared between agents
and get exhausted early.

ANY local business without a website is a customer — not just restaurants.
CATEGORIES below is deliberately broad: trades, salons, auto, retail, clinics.

    python3 scripts/free_leads.py miami                 # look, write nothing
    python3 scripts/free_leads.py miami --out leads.json
    python3 scripts/free_leads.py miami --insert        # write to the DB

Insert is deduped against existing lead names AND against phone numbers,
because OSM rows carry no google_place_id for the UNIQUE constraint to catch.
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

# Any business that plausibly serves walk-in local customers and might lack a
# site. Grouped only for readability; the query treats them as one set.
CATEGORIES = {
    "amenity": ["restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream",
                "dentist", "doctors", "clinic", "veterinary", "pharmacy",
                "driving_school", "childcare", "bank"],
    "shop": ["hairdresser", "beauty", "bakery", "butcher", "car_repair",
             "florist", "laundry", "dry_cleaning", "tattoo", "optician",
             "jewelry", "shoe_repair", "furniture", "hardware", "pet",
             "greengrocer", "convenience", "clothes", "mobile_phone",
             "car_parts", "bicycle", "electronics", "tyres"],
    "craft": ["plumber", "electrician", "carpenter", "roofer", "painter",
              "hvac", "locksmith", "gardener", "photographer", "caterer",
              "shoemaker", "tailor", "upholsterer", "stonemason",
              "pool_maintenance", "air_conditioning", "landscape_gardener",
              "handyman", "flooring", "window_construction", "pest_control",
              "sawmill", "glaziery", "metal_construction"],
    "leisure": ["fitness_centre", "swimming_pool"],
    "office": ["lawyer", "accountant", "insurance", "estate_agent"],
}


def bbox_for(city_key: str):
    """Roughly a city-sized box around the configured centre point."""
    city = C.CITIES.get(city_key)
    if not city:
        sys.exit(f"unknown city {city_key}; known: {', '.join(C.CITIES)}")
    lat, lng, pad = city["lat"], city["lng"], 0.13
    return (lat - pad, lng - pad * 1.25, lat + pad, lng + pad * 1.25)


def build_query(bbox) -> str:
    s, w, n, e = bbox
    parts = []
    for key, values in CATEGORIES.items():
        parts.append(f'  nwr["{key}"~"^({"|".join(values)})$"]({s},{w},{n},{e});')
    return "[out:json][timeout:180];\n(\n" + "\n".join(parts) + "\n);\nout tags center;"


def fetch(query: str) -> list:
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": "local-business-lead-research/1.0"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r).get("elements", [])


def tag(el, *keys) -> str:
    tags = el.get("tags", {})
    for k in keys:
        if tags.get(k):
            return tags[k].strip()
    return ""


def harvest(elements: list, city_key: str) -> list:
    """Keep only independent businesses with a phone and no web presence."""
    out = []
    for el in elements:
        name = tag(el, "name")
        phone = tag(el, "phone", "contact:phone")
        # Facebook counts as a website for our purposes: they have a presence,
        # so the pitch is different and the scanner classes them social_only.
        web = tag(el, "website", "contact:website", "url",
                  "facebook", "contact:facebook", "contact:instagram")
        if not name or not phone or web or C.is_chain(name):
            continue
        out.append({
            "name": name,
            "phone": phone,
            "email": tag(el, "contact:email", "email"),
            "address": " ".join(x for x in [tag(el, "addr:housenumber"),
                                            tag(el, "addr:street")] if x),
            "category": tag(el, "amenity", "shop", "craft", "office", "leisure"),
            "city": city_key,
            "lat": el.get("lat") or (el.get("center") or {}).get("lat"),
            "lon": el.get("lon") or (el.get("center") or {}).get("lon"),
        })
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _digits(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else d


def dedupe(rows: list) -> tuple:
    """Split into (new, already_known) against the live DB.

    Matches on normalized name OR last-10-digits of phone — OSM rows have no
    google_place_id, so the UNIQUE constraint cannot help here.
    """
    with db.conn() as c:
        known = c.execute("SELECT name, phone FROM leads").fetchall()
    names = {_norm(r[0]) for r in known}
    phones = {_digits(r[1]) for r in known if r[1]}
    new, dup = [], []
    seen_here = set()
    for r in rows:
        key = (_norm(r["name"]), _digits(r["phone"]))
        if key in seen_here:          # OSM lists some places twice (node + way)
            continue
        seen_here.add(key)
        if _norm(r["name"]) in names or (_digits(r["phone"]) in phones
                                         and _digits(r["phone"])):
            dup.append(r)
        else:
            new.append(r)
    return new, dup


def insert(rows: list) -> int:
    n = 0
    for r in rows:
        biz_id = db.upsert_business(
            name=r["name"], phone=r["phone"], address=r["address"],
            city=r["city"], area="", category=r["category"] or "business",
            rating=0, website="", website_status="none")
        if not biz_id:
            continue
        db.create_lead(biz_id, name=r["name"], phone=r["phone"],
                       email=r["email"], address=r["address"], city=r["city"],
                       area="", category=r["category"] or "business",
                       rating=0, website_status="none",
                       notes="source: openstreetmap/overpass (free)")
        n += 1
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("city", help="city key from config.CITIES, e.g. miami")
    p.add_argument("--out", help="write the harvested rows to this JSON file")
    p.add_argument("--insert", action="store_true", help="write new leads to the DB")
    p.add_argument("--limit", type=int, default=0, help="cap inserts")
    a = p.parse_args()

    rows = harvest(fetch(build_query(bbox_for(a.city))), a.city)
    new, dup = dedupe(rows)
    print(f"{a.city}: {len(rows)} businesses with a phone and no website")
    print(f"  already in DB: {len(dup)}")
    print(f"  new:           {len(new)}")
    by_cat = {}
    for r in new:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print("  by category:   " + ", ".join(
        f"{k}={v}" for k, v in sorted(by_cat.items(), key=lambda x: -x[1])[:12]))

    if a.out:
        Path(a.out).write_text(json.dumps(new, indent=1))
        print(f"  wrote {a.out}")
    if a.insert:
        batch = new[:a.limit] if a.limit else new
        print(f"  inserted {insert(batch)} leads")
    elif not a.out:
        for r in new[:10]:
            print(f"    {r['name'][:32]:32} {r['phone']:18} {r['category']}")
        print("  (preview only — use --insert to write, --out to save)")


if __name__ == "__main__":
    main()
