"""Houston restaurant scanner — finds businesses without websites"""
import requests
import time
import re
from config import GOOGLE_PLACES_API_KEY, SCAN_RADIUS_METERS
import db

PLACES_ENDPOINT = "https://maps.googleapis.com/maps/api/place"
TEXTSEARCH_URL = f"{PLACES_ENDPOINT}/textsearch/json"
NEARBYSEARCH_URL = f"{PLACES_ENDPOINT}/nearbysearch/json"
DETAILS_URL = f"{PLACES_ENDPOINT}/details/json"

HOUSTON_CENTER = {"lat": 29.7604, "lng": -95.3698}

# Keywords that suggest a restaurant is independent/family-owned
INDEPENDENT_KEYWORDS = [
    "taqueria", "taco", "pho", "banh mi", "sushi", "ramen", "pizza",
    "burger", "sandwich", "cafe", "bakery", "diner", "grill", "bbq",
    "mexican", "vietnamese", "chinese", "thai", "indian", "italian",
    "mediterranean", "greek", "soul food", "seafood", "steakhouse",
    "halal", "deli", "noodle", "hot dog", "ice cream", "donut",
    "fried chicken", "wing", "poboy", "crawfish", "gumbo", "tamale"
]

CHAIN_RESTAURANTS = [
    "mcdonald", "wendy", "burger king", "taco bell", "kfc", "pizza hut",
    "domino", "subway", "chick-fil-a", "starbuck", "dunkin", "whataburger",
    "chipotle", "panera", "jimmy john", "papa john", "little caesar"
]

def is_independent(name):
    name_lower = name.lower()
    for chain in CHAIN_RESTAURANTS:
        if chain in name_lower:
            return False
    for kw in INDEPENDENT_KEYWORDS:
        if kw in name_lower:
            return True
    return False

def has_website_simple(place_id, name):
    """Check if a place has a website via Google Places details"""
    params = {
        "place_id": place_id,
        "fields": "website,formatted_phone_number,opening_hours,price_level,rating,user_ratings_total,types",
        "key": GOOGLE_PLACES_API_KEY
    }
    try:
        resp = requests.get(DETAILS_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "OK":
            result = data.get("result", {})
            website = result.get("website")
            return {
                "has_website": website is not None,
                "website": website or "",
                "phone": result.get("formatted_phone_number", ""),
                "rating": result.get("rating"),
                "price_level": result.get("price_level"),
                "user_ratings_total": result.get("user_ratings_total"),
                "types": result.get("types", []),
            }
    except Exception as e:
        print(f"  Error checking {name}: {e}")
    return {"has_website": False, "website": ""}

def scan_area_houston(area_name, lat=None, lng=None):
    """Scan a Houston area for restaurants without websites"""
    print(f"\n🔍 Scanning: {area_name}...")
    
    # First get the location for the area
    geo_params = {
        "query": f"{area_name} Houston Texas",
        "key": GOOGLE_PLACES_API_KEY
    }
    try:
        geo_resp = requests.get(TEXTSEARCH_URL, params=geo_params, timeout=10)
        geo_data = geo_resp.json()
        if geo_data.get("status") != "OK" or not geo_data.get("results"):
            print(f"  Could not find {area_name}")
            return 0
        
        location = geo_data["results"][0]["geometry"]["location"]
        search_lat, search_lng = location["lat"], location["lng"]
    except Exception as e:
        print(f"  Geo lookup failed: {e}")
        return 0

    # Now search for restaurants nearby
    all_results = []
    food_types = ["restaurant", "mexican restaurant", "chinese restaurant", "vietnamese restaurant",
                  "pizza restaurant", "sushi restaurant", "bbq restaurant", "thai restaurant",
                  "indian restaurant", "seafood restaurant"]
    
    seen_names = set()
    
    for food_type in food_types:
        params = {
            "location": f"{search_lat},{search_lng}",
            "radius": SCAN_RADIUS_METERS,
            "type": "restaurant",
            "keyword": food_type,
            "key": GOOGLE_PLACES_API_KEY
        }
        try:
            resp = requests.get(NEARBYSEARCH_URL, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "OK":
                for r in data.get("results", []):
                    name = r.get("name", "")
                    if name not in seen_names:
                        seen_names.add(name)
                        all_results.append(r)
        except Exception as e:
            print(f"  Search error: {e}")
        time.sleep(0.3)  # Rate limiting

    print(f"  Found {len(all_results)} unique places")

    # Check each for website
    leads_found = 0
    for place in all_results:
        name = place.get("name", "")
        place_id = place.get("place_id", "")
        
        if not is_independent(name):
            continue
        
        details = has_website_simple(place_id, name)
        
        if not details.get("has_website"):
            place_data = {
                "place_id": place_id,
                "name": name,
                "address": place.get("vicinity", ""),
                "phone": details.get("phone", ""),
                "rating": details.get("rating"),
                "price_level": details.get("price_level"),
                "user_ratings_total": details.get("user_ratings_total"),
                "types": details.get("types", []),
                "website": details.get("website", ""),
            }
            
            rid = db.add_restaurant(place_data)
            if rid:
                priority = 5 if details.get("rating", 0) >= 4.0 else 3
                db.add_lead(rid, priority)
                leads_found += 1
                print(f"  🎯 LEAD: {name} — {place.get('vicinity','')} {'★' + str(details.get('rating','?')) if details.get('rating') else ''}")
        
        time.sleep(0.2)  # Rate limiting

    db.log_scan(area_name, len(all_results), leads_found)
    print(f"  ✅ {area_name}: {leads_found} new leads")
    return leads_found

def scan_all_houston():
    """Scan all Houston areas"""
    from config import HOUSTON_AREAS
    total = 0
    for area in HOUSTON_AREAS:
        leads = scan_area_houston(area)
        total += leads
        time.sleep(2)  # Be nice to Google
    print(f"\n🏁 Scan complete! {total} total leads found")
    return total
