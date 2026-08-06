"""
LocationIQ (OSM-based) scanner.

Finds independent businesses whose web presence is missing or social-only —
those are the ones a demo site is actually useful to. Businesses with a real
website are skipped, not pitched.

  python -m scanner.scanner --city houston
  python -m scanner.scanner --all
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from config import (BUSINESS_CATEGORIES, CHAIN_NAMES, CITIES, DEFAULT_CATEGORIES, DEFAULT_CITIES,
                    GOOGLE_PLACES_API_KEY, LOCATIONIQ_API_KEY, category_for_types,
                    get_city)

NEARBY_URL = "https://us1.locationiq.com/v1/nearby"
LOOKUP_URL = "https://us1.locationiq.com/v1/lookup"
GOOGLE_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

OSM_TYPE_PREFIX = {"node": "N", "way": "W", "relation": "R"}

# OSM tags that carry a business's own site, checked in priority order.
WEBSITE_TAGS = ("website", "contact:website", "url")
PHONE_TAGS = ("phone", "contact:phone")

# A Facebook/Instagram page is not a website — those businesses are the target.
SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linktr.ee", "yelp.com",
                "doordash.com", "ubereats.com", "grubhub.com", "toasttab.com",
                "square.site", "wixsite.com/blank", "business.site", "m.me")


def _get(url: str, params: dict) -> list:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        print(f"    ! LocationIQ {e.code}: {detail}")
        return []
    except Exception as e:
        print(f"    ! request failed: {e}")
        return []


def classify_website(url: str) -> str:
    """none | social_only | has_site"""
    if not url:
        return "none"
    low = url.lower()
    if any(h in low for h in SOCIAL_HOSTS):
        return "social_only"
    return "has_site"


def google_enrich(name: str, address: str) -> dict:
    """Google Places lookup for one business → {phone, website, website_status,
    rating}. LocationIQ/OSM almost never carries phone/website for small shops,
    so the scanner leans on Google for real contact data. Returns empty dict on
    no key / no match / failure — caller keeps whatever LocationIQ gave it."""
    if not GOOGLE_PLACES_API_KEY:
        return {}
    body = json.dumps({
        "textQuery": f"{name}, {address}",
        "maxResultCount": 1,
    }).encode()
    req = urllib.request.Request(GOOGLE_SEARCH_URL, body, {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.websiteUri,places.nationalPhoneNumber,places.rating",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception as e:
        print(f"    ! Google enrich failed: {e}")
        return {}
    places = data.get("places") or []
    if not places:
        return {}
    p = places[0]
    website = p.get("websiteUri", "") or ""
    return {"phone": p.get("nationalPhoneNumber", "") or "",
            "website": website,
            "website_status": classify_website(website),
            "rating": p.get("rating")}


def verify_website(name: str, address: str) -> str:
    """One-off Google Places lookup for a single business, used only right before
    emailing a lead — LocationIQ's free OSM data under-reports websites, so this
    catches leads that were wrongly flagged as having none.

    Returns the website URL if a real (non-social) site is found, "" if confirmed
    clean or the check is inconclusive (no key, no match, request failure) — callers
    should treat "" as "safe to proceed", not as proof of no website.
    """
    info = google_enrich(name, address)
    website = info.get("website", "")
    return website if classify_website(website) == "has_site" else ""


def scan_area(area_name: str, city: str = "houston", category: str = "restaurant",
              max_results: int = 20) -> int:
    """Scan one area of one city for one category. Returns count of new leads."""
    if not LOCATIONIQ_API_KEY:
        print("  ! LOCATIONIQ_API_KEY not set — cannot scan")
        return 0

    meta = BUSINESS_CATEGORIES.get(category, BUSINESS_CATEGORIES["restaurant"])
    coords = get_city(city)["areas"].get(area_name)
    if not coords:
        print(f"    {area_name} / {category}: no known coordinates for this area")
        return 0
    lat, lon = coords

    # /nearby finds real POIs by tag, but never returns extratags (website/phone).
    places = _get(NEARBY_URL, {
        "key": LOCATIONIQ_API_KEY, "lat": lat, "lon": lon,
        "tag": meta["types"][0], "radius": 3000, "format": "json",
        "addressdetails": 1, "limit": min(max_results, 50),
    })
    print(f"    {area_name} / {category}: {len(places)} results", end="")

    # Batch-fetch extratags (website/phone) for everything /nearby found, one call.
    osm_ids = [f"{OSM_TYPE_PREFIX.get(p.get('osm_type'), 'N')}{p.get('osm_id')}"
               for p in places if p.get("osm_id")]
    extratags_by_id = {}
    if osm_ids:
        time.sleep(0.6)
        details = _get(LOOKUP_URL, {
            "key": LOCATIONIQ_API_KEY, "osm_ids": ",".join(osm_ids),
            "format": "json", "extratags": 1,
        })
        for d in details:
            extratags_by_id[d.get("osm_id")] = d.get("extratags") or {}

    new = 0
    for p in places:
        extratags = extratags_by_id.get(p.get("osm_id"), {})
        website = next((extratags[t] for t in WEBSITE_TAGS if extratags.get(t)), "")
        status = classify_website(website)

        name = (p.get("name") or "").strip()
        if not name:
            continue
        if name.lower() in CHAIN_NAMES:
            continue

        phone = next((extratags[t] for t in PHONE_TAGS if extratags.get(t)), "")
        osm_id = f"{p.get('osm_type', 'osm')}/{p.get('osm_id') or p.get('place_id')}"
        types = [p.get("type"), p.get("class")]

        # OSM rarely has phone/website for small shops — backfill from Google.
        info = google_enrich(name, p.get("display_name", ""))
        if info:
            phone = phone or info.get("phone", "")
            website = website or info.get("website", "")
            status = info.get("website_status") or status
            rating = info.get("rating")
        else:
            rating = None

        if status == "has_site":
            continue  # already has a real site — not our customer

        bid = db.upsert_business(
            google_place_id=osm_id,
            name=name,
            phone=phone,
            email="",  # never returned by place search; collected manually or enriched later
            address=p.get("display_name", ""),
            city=city,
            area=area_name,
            category=category_for_types(types) or category,
            rating=rating,
            review_count=None,
            website=website,
            website_status=status,
        )
        if bid is None:
            continue  # already in the DB

        db.create_lead(
            bid, name=name, phone=phone, email="",
            address=p.get("display_name", ""), city=city, area=area_name,
            category=category_for_types(types) or category,
            rating=rating, website_status=status)
        new += 1

    print(f" → {new} new")
    return new


def scan_city(city_key: str, categories=None, max_areas: int = 8) -> int:
    """Scan several areas x categories for one city. Returns total new leads."""
    city_key = (city_key or "houston").lower()
    if city_key not in CITIES:
        print(f"unknown city: {city_key}")
        return 0
    categories = categories or DEFAULT_CATEGORIES
    city = CITIES[city_key]
    areas = list(city["areas"])[:max_areas]

    print(f"\n=== {city['name']}, {city['state']} — {len(areas)} areas x {len(categories)} categories ===")
    total = 0
    for area in areas:
        for cat in categories:
            total += scan_area(area, city=city_key, category=cat)
            time.sleep(1.0)  # stay under LocationIQ's free-tier 2 req/s, 60 req/min cap
    print(f"=== {city['name']}: {total} new leads ===")
    return total


def daily_scan_sample(budget: int = 12, cities=None, categories=None) -> int:
    """Scan a random slice of the full (city, area, category) space instead of
    the whole thing — a full sweep is thousands of LocationIQ calls, way past
    what one scheduled run should do. google_place_id is UNIQUE, so re-rolling
    a combo already scanned before just costs a wasted call, not a duplicate
    lead — safe to pick randomly each run rather than track a cursor."""
    import random
    cities = cities or DEFAULT_CITIES
    categories = categories or DEFAULT_CATEGORIES

    combos = [(city, area, cat) for city in cities if city in CITIES
              for area in CITIES[city]["areas"] for cat in categories]
    random.shuffle(combos)

    total = 0
    for city, area, cat in combos[:budget]:
        total += scan_area(area, city=city, category=cat)
        time.sleep(1.0)
    print(f"=== daily sample: {total} new leads from {min(budget, len(combos))} areas ===")
    return total


def scan_multiple(cities=None, categories=None, max_areas_per_city: int = 5) -> int:
    cities = cities or DEFAULT_CITIES
    total = 0
    for ck in cities:
        total += scan_city(ck, categories=categories, max_areas=max_areas_per_city)
    print(f"\nTOTAL new leads: {total}")
    return total


def main():
    ap = argparse.ArgumentParser(description="Scan for businesses without real websites")
    ap.add_argument("--city", help="city key, e.g. houston")
    ap.add_argument("--all", action="store_true", help="scan the default city set")
    ap.add_argument("--category", action="append", help="repeatable; defaults to config set")
    ap.add_argument("--areas", type=int, default=8, help="max areas per city")
    ap.add_argument("--selftest", action="store_true",
                    help="verify google_enrich returns contact data, then exit")
    args = ap.parse_args()

    if args.selftest:
        r = google_enrich("Uchi", "904 Westheimer Road, Houston TX")
        assert r.get("phone"), f"expected a phone from Google, got: {r}"
        print("OK google_enrich ->", r["website"], r["phone"])
        return

    db.init_db()
    cats = args.category or DEFAULT_CATEGORIES

    if args.all:
        scan_multiple(categories=cats, max_areas_per_city=args.areas)
    elif args.city:
        scan_city(args.city, categories=cats, max_areas=args.areas)
    else:
        ap.print_help()
        print("\ncities:", ", ".join(CITIES))
        print("categories:", ", ".join(BUSINESS_CATEGORIES))
        return

    print(json.dumps(db.get_stats(), indent=2, default=str))


if __name__ == "__main__":
    main()
