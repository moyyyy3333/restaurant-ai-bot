#!/usr/bin/env python3
"""Send the 5 restaurant outreach emails"""
import requests, json

from config import RESEND_API_KEY as RESEND_KEY
FROM = "M O <onboarding@resend.dev>"
REPLY_TO = "iconcre8tion@gmail.com"

restaurants = [
    {
        "name": "Enjels African Restaurant, Grocery & Lounge",
        "email": "enjelsafrican@gmail.com",
        "phone": "281-473-7322",
        "token": "271bcd4fd6cabe7ec983b78b"
    },
    {
        "name": "Di An Pho",
        "email": "dianpho@gmail.com",
        "phone": "281-896-0002",
        "token": "745c911bcdfb4a4e9064eb5b"
    },
    {
        "name": "Houston Made (Food Truck)",
        "email": "houstonmadeburgers@gmail.com",
        "phone": "832-560-5669",
        "token": "91e2362f3ad5c161db794bf6"
    },
    {
        "name": "Taqueria El Huache",
        "email": "taqueriaelhuache@gmail.com",
        "phone": "281-746-8310",
        "token": "194c7bf912cd3d1600b1bf4b"
    },
    {
        "name": "OMG Baked Potatoes (Food Truck)",
        "email": "omgbakedpotatoes@gmail.com",
        "phone": "832-819-4664",
        "token": "f81315619fc1e1b456ac4f53"
    }
]

headers = {
    'Authorization': f'Bearer {RESEND_KEY}',
    'Content-Type': 'application/json'
}

results = []

for r in restaurants:
    from config import DEMO_BASE_URL
    demo_url = f"{DEMO_BASE_URL}/demo/{r['token']}"
    
    subject = f"New website built for {r['name']} — free preview"
    body = f"""Hi there,

We noticed {r['name']} doesn't have a website yet. In 2026, 87% of diners search online before choosing where to eat — and if they can't find you online, they go to your competitor.

I built a custom website for {r['name']} — completely free to preview:

🔗 {demo_url}

Your site includes:
• Full menu with photos
• Click-to-call ordering button
• Hours & location
• Mobile-friendly design
• SEO so customers find you on Google

All for just $299 one-time. Includes custom domain, hosting, and search engine listing.

This preview expires in 72 hours.

Reply to this email or call for questions.

Best,
M O
iconcre8tion@gmail.com
"""

    payload = {
        'from': FROM,
        'to': [r['email']],
        'reply_to': REPLY_TO,
        'subject': subject,
        'text': body
    }
    
    try:
        resp = requests.post('https://api.resend.com/emails', headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            email_id = resp.json().get('id', 'unknown')
            print(f'✅ {r["name"]} → {r["email"]} — SENT (ID: {email_id})')
            results.append({'name': r['name'], 'email': r['email'], 'status': 'sent', 'id': email_id})
        else:
            print(f'❌ {r["name"]} → {r["email"]} — FAILED ({resp.status_code}): {resp.text[:150]}')
            results.append({'name': r['name'], 'email': r['email'], 'status': 'failed', 'error': resp.text[:150]})
    except Exception as e:
        print(f'⚠️ {r["name"]} → {r["email"]} — ERROR: {e}')
        results.append({'name': r['name'], 'email': r['email'], 'status': 'error', 'error': str(e)})

print("\n" + "="*60)
print("📋 FINAL RESULTS:")
for r in results:
    icon = "✅" if r['status'] == 'sent' else "❌"
    print(f"  {icon} {r['name']}: {r['status'].upper()}")
print(f"\nTotal sent: {sum(1 for r in results if r['status'] == 'sent')}/{len(results)}")

with open('/tmp/outreach_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nResults saved to /tmp/outreach_results.json")
