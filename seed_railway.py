#!/usr/bin/env python3
"""
Seed Railway deployment with local database data.
Usage: python3 seed_railway.py [base_url]
"""
import sys, os, json, requests, uuid

sys.path.insert(0, os.path.dirname(__file__))
import db

# Railway deployment URL
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://restaurant-ai-bot-production.up.railway.app"
SEED_TOKEN = os.environ.get("SEED_TOKEN", "restaurant-bot-seed-2026")

def dump_local_db():
    """Dump local SQLite DB to JSON"""
    conn = db.get_db()

    restaurants = []
    for r in conn.execute("SELECT * FROM restaurants").fetchall():
        restaurants.append(dict(r))

    leads = []
    for l in conn.execute("SELECT * FROM leads").fetchall():
        leads.append(dict(l))

    sites = []
    for s in conn.execute("SELECT * FROM generated_sites").fetchall():
        s = dict(s)
        s["html_content"] = s.get("html_content") or ""
        sites.append(s)

    return {"restaurants": restaurants, "leads": leads, "sites": sites}


def upload_data(data):
    """POST data to Railway seed endpoint"""
    url = f"{BASE_URL}/admin/seed"
    headers = {
        "Content-Type": "application/json",
        "X-Seed-Token": SEED_TOKEN
    }

    print(f"📤 Uploading {len(data['restaurants'])} restaurants, {len(data['leads'])} leads, {len(data['sites'])} sites...")
    print(f"   To: {url}")

    try:
        resp = requests.post(url, json=data, headers=headers, timeout=30)
        print(f"   Response: HTTP {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ Imported: {result.get('imported', {})}")
        else:
            print(f"   ❌ Error: {resp.text[:500]}")
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot reach {BASE_URL}")
        print(f"   Is the Railway service running?")
        return False


def main():
    print(f"🔌 Restaurant AI Bot — Database Seed Tool")
    print(f"   Target: {BASE_URL}\n")

    # Dump local DB
    print("📦 Dumping local database...")
    data = dump_local_db()
    print(f"   Found: {len(data['restaurants'])} restaurants, {len(data['leads'])} leads, {len(data['sites'])} sites\n")

    # Upload to Railway
    if upload_data(data):
        print(f"\n✅ Database seeded successfully!")
        print(f"   Demo server: {BASE_URL}")
        print(f"   Demo links will work at: {BASE_URL}/demo/<token>")
    else:
        print(f"\n❌ Seeding failed")


if __name__ == "__main__":
    main()
