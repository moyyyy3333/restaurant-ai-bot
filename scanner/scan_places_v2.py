"""Scanner using New Places API (v1) with service account auth"""
import requests, json, time, sys, os, jwt as pyjwt
from datetime import datetime
sys.path.insert(0, '..')
import db
from config import HOUSTON_AREAS

# Service account auth — load from deployed secrets file or env var
SECRETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "secrets")
SA_FILE = os.path.join(SECRETS_DIR, "gcp_sa.b64")
SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "")

def get_access_token():
    """Get OAuth access token from service account credentials"""
    sa_json = SERVICE_ACCOUNT_JSON
    if not sa_json and os.path.exists(SA_FILE):
        import base64
        with open(SA_FILE) as f:
            sa_json = base64.b64decode(f.read()).decode()
    try:
        sa = json.loads(sa_json)
        iat = int(time.time())
        claims = {
            'iss': sa['client_email'],
            'sub': sa['client_email'],
            'aud': 'https://oauth2.googleapis.com/token',
            'iat': iat,
            'exp': iat + 3600,
            'scope': 'https://www.googleapis.com/auth/cloud-platform'
        }
        assertion = pyjwt.encode(claims, sa['private_key'], algorithm='RS256')
        r = requests.post('https://oauth2.googleapis.com/token', data={
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': assertion
        }, timeout=10)
        return r.json().get('access_token')
    except Exception as e:
        print(f"  ❌ Auth error: {e}")
        return None

URL = 'https://places.googleapis.com/v1/places:searchText'
FIELDS = 'places.displayName,places.formattedAddress,places.id,places.rating,places.websiteUri,places.internationalPhoneNumber,places.priceLevel,places.userRatingCount'

def search_restaurants(query, max_results=20):
    """Search for restaurants using New Places API with OAuth"""
    token = get_access_token()
    if not token:
        return []
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'X-Goog-FieldMask': FIELDS
    }
    body = {
        'textQuery': query,
        'maxResultCount': max_results
    }
    r = requests.post(URL, headers=headers, json=body, timeout=15)
    if r.status_code == 200:
        return r.json().get('places', [])
    else:
        print(f"  ❌ API error: {r.status_code} — {r.text[:200]}")
        return []

def scan_area(area_name):
    """Scan a specific Houston area for restaurants without websites"""
    print(f"\n📍 Scanning {area_name}...")
    
    queries = [
        f"restaurants in {area_name} Houston Texas",
        f"food {area_name} Houston TX",
        f"Mexican food {area_name} Houston",
        f"tacos {area_name} Houston",
        f"pho {area_name} Houston",
        f"pizza {area_name} Houston",
        f"Chinese food {area_name} Houston"
    ]
    
    found = []
    seen_ids = set()
    
    for query in queries:
        places = search_restaurants(query)
        for p in places:
            pid = p.get('id', '')
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            
            name = p.get('displayName', {}).get('text', '?')
            types = p.get('placeTypes', [])
            
            # Skip chains
            skip_keywords = ['mcdonald', 'burger king', 'wendy', 'subway', 'taco bell', 'chick-fil-a', 
                           'domino', 'pizza hut', 'papa john', 'kfc', 'dunkin', 'starbucks']
            if any(k in name.lower() for k in skip_keywords):
                continue
            
            # Check for website
            has_website = bool(p.get('websiteUri'))
            web = p.get('websiteUri', '')
            
            # Also skip if it has a real website (not just social media)
            if has_website:
                social_domains = ['instagram.com', 'facebook.com', 'yelp.com', 'tripadvisor.com']
                is_social_only = any(d in (web or '').lower() for d in social_domains)
                if not is_social_only:
                    continue  # They have a real website, not a lead
            
            found.append({
                'place_id': pid,
                'name': name,
                'address': p.get('formattedAddress', ''),
                'phone': p.get('internationalPhoneNumber', ''),
                'rating': p.get('rating', 0),
                'website': web or '',
                'types': types,
                'price_level': p.get('priceLevel', 0),
                'user_ratings_total': p.get('userRatingCount', 0)
            })
            
            if len(found) >= 20:  # Max 20 no-website per area
                break
        time.sleep(0.2)  # Rate limit
    
    # Save to DB
    new_leads = 0
    for r in found:
        rid = db.add_restaurant(r)
        lid = db.add_lead(rid, priority=int(r['rating']) if r['rating'] else 3)
        if lid:
            new_leads += 1
        print(f"  {'📭' if not r['website'] else '📱'} {r['name']} — {r.get('rating', '?')}★ — {'NO SITE' if not r['website'] else 'Social only'}")
    
    return new_leads

def scan_all():
    """Scan all Houston areas"""
    db.init_db()
    total = 0
    for area in HOUSTON_AREAS:
        count = scan_area(area)
        total += count
        time.sleep(1)
    print(f"\n✅ Total new leads: {total}")
    return total

if __name__ == '__main__':
    scan_all()
