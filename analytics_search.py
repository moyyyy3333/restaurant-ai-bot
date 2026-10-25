#!/usr/bin/env python3
"""Graph scan: fan-out city searches (concurrent HTTP, capped), reduce/dedupe in code,
then rank no-site prospects. Retry-on-429 so one quota burst doesn't drop a city.
"""
import json, os, sys, time, random
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import GOOGLE_PLACES_API_KEY

SLURL = "https://places.googleapis.com/v1/places:searchText"
MAX_WORKERS = 6          # bounded fan-out
CITIES = ["Conroe","Katy","Pearland","Galveston","College Station","Sugar Land",
    "The Woodlands","Round Rock","Temple","Bryan","Savannah","Charleston","Gulfport",
    "Pensacola","Gainesville","Asheville","Knoxville","Birmingham","Baton Rouge",
    "Hattiesburg","Evansville","Bloomington","Rockford","Madison","Ann Arbor","Toledo",
    "Dayton","Iowa City","Fargo","Flagstaff","Tucson","Albuquerque","El Paso","Fresno",
    "Bakersfield","Reno","Boise","Ogden","Colorado Springs","Concord","Burlington",
    "Portland","New Haven","Providence","Harrisburg","Buffalo","Syracuse","Newark",
    "Spokane","Eugene","Salem","Missoula","Billings","Anchorage","Honolulu"]
QUERIES = ["restaurants in {c}", "coffee shops in {c}", "barbecue in {c}",
    "diner in {c}", "deli in {c}", "tacos in {c}"]

def _req(url, body, headers):
    import urllib.request
    req = urllib.request.Request(url, body, headers)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

def search(city, query):
    full = " ".join(query.format(c=city).split())
    body = json.dumps({"textQuery": full, "maxResultCount": 15}).encode()
    hdr = {"Content-Type":"application/json","X-Goog-Api-Key":GOOGLE_PLACES_API_KEY,
           "X-Goog-FieldMask":"places.displayName,places.websiteUri,places.nationalPhoneNumber,places.rating,places.formattedAddress"}
    for attempt in range(4):
        try:
            return _req(SLURL, body, hdr).get("places") or []
        except Exception as e:
            code = getattr(e, "code", 0)
            if code == 429:
                time.sleep(4 + attempt*7 + random.uniform(0,2))
                continue
            return []
    return []

def classify(url):
    low = (url or "").lower()
    if not low:
        return "none"
    social = ("facebook.com","instagram.com","yelp.com","tripadvisor","tiktok.com","twitter.com")
    return "social_only" if any(h in low for h in social) else "has_site"

def fan_out():
    tasks = [(c, q) for c in CITIES for q in QUERIES]
    results = {}          # (city, name) -> record
    tot = len(tasks)
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(search, c, q): (c,q) for c,q in tasks}
        for fut in as_completed(futs):
            c, q = futs[fut]
            done += 1
            for p in (fut.result() or []):
                name = (p.get("displayName") or {}).get("text","").strip()
                if not name:
                    continue
                key = (c, name.lower())
                if key in results:
                    continue
                results[key] = {
                    "city": c, "name": name,
                    "status": classify(p.get("websiteUri")),
                    "phone": p.get("nationalPhoneNumber","") or "",
                    "addr": (p.get("formattedAddress","") or ""),
                }
            if done % 100 == 0 or done == tot:
                print(f"  {done}/{tot}", flush=True)
    return list(results.values())

def reduce_and_rank(records):
    seen = set()
    out = []
    for r in records:
        if r["name"].lower() in seen:
            continue
        seen.add(r["name"].lower())
        out.append(r)
    # barrier: needs whole set to rank
    targets = [r for r in out if r["status"] in ("none","social_only") and r["phone"]]
    targets.sort(key=lambda r: (r["status"]=="none", r["city"]))
    return targets

def main():
    print(f"fan-out: {len(CITIES)} cities x {len(QUERIES)} queries, {MAX_WORKERS} workers", flush=True)
    records = fan_out()
    targets = reduce_and_rank(records)
    lines = []
    head = f"===== {len(targets)} NO-WEBSITE / SOCIAL-ONLY (with phone), nationwide =====\n"
    print(head, flush=True)
    lines.append(head)
    for r in targets:
        tag = "" if r["status"]=="none" else " [SOCIAL]"
        line = f"{r['city']:20s} | {r['name'][:40]:40s} | {r['phone']:18s} | {r['addr'][:34]}{tag}"
        print(line); lines.append(line)
    with open("no_site_leads.txt","w") as f:
        f.write("\n".join(lines))
    print("\nsaved -> no_site_leads.txt")

if __name__ == "__main__":
    main()
