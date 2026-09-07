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

# Marketplaces and profiles are not a business's own site. Match on hostname
# only (not substring) so dishsociety.com / toutsuitehtx.com stay has_site.
# Branded ordering hosts (thanx.com, a shop's own toast page) are real sites.
SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linktr.ee", "yelp.com",
                "doordash.com", "ubereats.com", "grubhub.com",
                "wixsite.com", "business.site")
OWN_SITE_HOSTS = ("thanx.com", "dishsociety.com", "toutsuitehtx.com")


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


# Domains that serve a "this domain is for sale"/holding page. A business
# whose only web presence is one of these effectively has no website.
PARKED_HOSTS = ("sedoparking.com", "afternic.com", "godaddysites.com/parked",
                "parkingcrew.net", "bodis.com", "dan.com", "hugedomains.com")


def _norm_tokens(s: str) -> set:
    """Lowercase word set with punctuation and generic filler removed."""
    import re as _re
    stop = {"the", "and", "a", "of", "restaurant", "cafe", "coffee", "bar",
            "grill", "kitchen", "llc", "inc", "co"}
    # Drop apostrophes first so "Sam's" is one token, not "sam" + "s".
    flat = (s or "").lower().replace("'", "").replace("\u2019", "")
    words = _re.findall(r"[a-z0-9]+", flat)
    return {w for w in words if w not in stop}


def name_matches(queried: str, returned: str, threshold: float = 0.6) -> bool:
    """Is the place the API returned actually the business we asked about?

    Google's text search always returns *something*. Without this check a
    wrong match imports a wrong website (or a wrong absence of one), which is
    exactly how leads were mislabelled as having no site.
    """
    a, b = _norm_tokens(queried), _norm_tokens(returned)
    if not a or not b:
        return False
    return len(a & b) / len(min(a, b, key=len)) >= threshold


# A site that refuses automated clients is not the same as a site that is gone.
# Guessing "no website" from a bot block is exactly how a business with a
# perfectly good site gets told it has none.
BLOCKED_CODES = {401, 403, 405, 406, 429, 503}


def url_liveness(url: str, timeout: int = 8) -> str:
    """live | dead | unknown

    dead    - the page is genuinely gone (404/410, DNS failure, refused) or the
              domain is a parking page. Safe to treat as "no real website".
    unknown - the check was refused or timed out. We cannot tell, so we do not
              get to claim the business has no website.
    """
    if not url:
        return "dead"
    low = url.lower()
    if any(h in low for h in PARKED_HOSTS):
        return "dead"
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            final = (r.geturl() or "").lower()
            if any(h in final for h in PARKED_HOSTS):
                return "dead"
            return "live" if r.status < 400 else "unknown"
    except urllib.error.HTTPError as e:
        if e.code in BLOCKED_CODES:
            return "unknown"
        return "dead" if e.code in (404, 410) else "unknown"
    except urllib.error.URLError as e:
        # DNS failure / connection refused = really gone; timeouts = can't tell.
        reason = str(getattr(e, "reason", "")).lower()
        if "name or service not known" in reason or "nodename nor servname" in reason \
           or "connection refused" in reason:
            return "dead"
        return "unknown"
    except Exception:
        return "unknown"


def url_is_live(url: str, timeout: int = 8) -> bool:
    """Back-compat boolean. Prefer url_liveness() — this collapses
    'cannot tell' into False."""
    return url_liveness(url, timeout) == "live"


def _hostname(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower()


def _host_is(host: str, needles) -> bool:
    for needle in needles:
        n = needle.lower().lstrip(".")
        if host == n or host.endswith("." + n):
            return True
    return False


def classify_website(url: str, *, source_answered: bool = True) -> str:
    """has_site | social_only | none | unknown

    `none` is a CLAIM that the business has no website, so it is only returned
    when a lookup actually answered. If nothing authoritative was consulted,
    the honest answer is `unknown` — and unknown is never pitched.
    """
    if not url:
        return "none" if source_answered else "unknown"
    host = _hostname(url)
    if _host_is(host, OWN_SITE_HOSTS):
        return "has_site"
    if _host_is(host, SOCIAL_HOSTS) or host == "m.me":
        return "social_only"
    # Legacy path-only markers (blank Wix) still count as not a real site.
    low = url.lower()
    if "wixsite.com/blank" in low:
        return "social_only"
    return "has_site"


def hours_from_descriptions(descriptions) -> list:
    """Turn Google weekdayDescriptions into (day, hours) rows.

    Invents nothing: empty or unparseable input → []. Consecutive days with
    the same hours are collapsed (Mon – Sat) so the table stays readable.
    """
    rows = []
    for line in descriptions or []:
        line = (line or "").strip()
        if not line or ":" not in line:
            continue
        day, _, rest = line.partition(":")
        day, rest = day.strip(), rest.strip()
        if day and rest:
            rows.append((day, rest))
    if not rows:
        return []
    groups = []
    start, prev_time = rows[0][0], rows[0][1]
    last = start
    for day, time in rows[1:]:
        if time == prev_time:
            last = day
            continue
        groups.append((_day_span(start, last), prev_time))
        start, last, prev_time = day, day, time
    groups.append((_day_span(start, last), prev_time))
    return groups


def _day_span(start: str, end: str) -> str:
    if start == end:
        return start
    short = lambda d: (d[:3] if len(d) > 3 else d)
    return f"{short(start)} – {short(end)}"


def types_from_place(place: dict) -> list:
    """primaryType + display name + types, de-duplicated, order kept."""
    out = []
    if place.get("primaryType"):
        out.append(str(place["primaryType"]))
    disp = ((place.get("primaryTypeDisplayName") or {}).get("text") or "")
    if disp:
        out.append(disp)
    for t in place.get("types") or []:
        if t:
            out.append(str(t))
    seen, uniq = set(), []
    for t in out:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(t)
    return uniq


_ENRICH_CACHE: dict = {}

# Website checks keep the 20s default. Demo rebuild uses a short timeout so a
# slow Places call cannot hang /demo/{token}.
_PLACE_FIELD_MASK = (
    "places.websiteUri,places.nationalPhoneNumber,places.rating,"
    "places.displayName,places.regularOpeningHours,places.primaryType,"
    "places.types,places.primaryTypeDisplayName,places.googleMapsLinks"
)


def google_enrich(name: str, address: str, timeout: int = 20,
                  check_liveness: bool = True) -> dict:
    """Google Places lookup for one business → {phone, website, website_status,
    rating, hours, types}. LocationIQ/OSM almost never carries phone/website
    for small shops, so the scanner leans on Google for real contact data.
    Returns empty dict on no key / no match / failure — caller keeps whatever
    LocationIQ gave it. Hours are omitted (not invented) when Google has none.
    """
    if not GOOGLE_PLACES_API_KEY:
        return {}
    cache_key = (name.lower().strip(), (address or "").lower().strip(),
                 int(timeout), bool(check_liveness))
    cached = _ENRICH_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)
    body = json.dumps({
        "textQuery": f"{name}, {address}",
        "maxResultCount": 1,
    }).encode()
    req = urllib.request.Request(GOOGLE_SEARCH_URL, body, {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _PLACE_FIELD_MASK,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception as e:
        print(f"    ! Google enrich failed: {e}")
        return {}
    places = data.get("places") or []
    if not places:
        # Google answered and knows of no such business. That is not evidence
        # about a website either way.
        return {}
    p = places[0]
    returned_name = ((p.get("displayName") or {}).get("text")) or ""
    if returned_name and not name_matches(name, returned_name):
        print(f"    ~ Google returned '{returned_name}' for '{name}' — treating as no match")
        return {}
    website = p.get("websiteUri", "") or ""
    status = classify_website(website, source_answered=True)
    if website and status == "has_site" and check_liveness:
        live = url_liveness(website)
        if live == "dead":
            print(f"    ~ {name}: listed site {website} is dead/parked")
            website, status = "", "none"
        elif live == "unknown":
            # The site exists on paper but refused our check. Do not pitch.
            print(f"    ~ {name}: {website} could not be verified — leaving unknown")
            status = "unknown"
    hours = hours_from_descriptions(
        ((p.get("regularOpeningHours") or {}).get("weekdayDescriptions")) or [])
    maps = p.get("googleMapsLinks") or {}
    result = {"phone": p.get("nationalPhoneNumber", "") or "",
              "website": website,
              "website_status": status,
              "rating": p.get("rating"),
              "hours": hours,
              "types": types_from_place(p),
              "maps_links": maps}
    _ENRICH_CACHE[cache_key] = result
    return dict(result)


def verify_website(name: str, address: str) -> str:
    """Back-compat wrapper: returns a real site URL, or "" otherwise.

    Prefer check_website() — this collapses "confirmed no site" and "could not
    tell" into the same empty string, which is what caused leads with websites
    to be pitched as having none.
    """
    status, url = check_website(name, address)
    return url if status == "has_site" else ""


def check_website(name: str, address: str) -> tuple:
    """Authoritative tri-state check for one business.

    Returns (status, url) where status is has_site | social_only | none |
    unknown. Only `none` and `social_only` are safe to pitch; `unknown` means
    the check could not answer and the lead must not be contacted yet.
    """
    if not GOOGLE_PLACES_API_KEY:
        return ("unknown", "")
    info = google_enrich(name, address)
    if not info:
        return ("unknown", "")
    url = info.get("website", "")
    return (info.get("website_status") or classify_website(url, source_answered=True), url)


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
