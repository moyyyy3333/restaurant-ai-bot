#!/usr/bin/env python3
"""Send all 5 restaurant outreach emails"""
import requests, json

# Full Resend key from Morpheus
RESEND_KEY = "re_VVi1Ee55_8jw3giJjcEMUueKqHa5e2rvb"
FROM = "M O <onboarding@resend.dev>"
REPLY_TO = "iconcre8tion@gmail.com"

restaurants = [
    ("Enjels African Restaurant, Grocery & Lounge", "enjelsafrican@gmail.com", "281-473-7322", "271bcd4fd6cabe7ec983b78b"),
    ("Di An Pho", "dianpho@gmail.com", "281-896-0002", "745c911bcdfb4a4e9064eb5b"),
    ("Houston Made (Food Truck)", "houstonmadeburgers@gmail.com", "832-560-5669", "91e2362f3ad5c161db794bf6"),
    ("Taqueria El Huache", "taqueriaelhuache@gmail.com", "281-746-8310", "194c7bf912cd3d1600b1bf4b"),
    ("OMG Baked Potatoes (Food Truck)", "omgbakedpotatoes@gmail.com", "832-819-4664", "f81315619fc1e1b456ac4f53"),
]

headers = {
    'Authorization': f'Bearer {RESEND_KEY}',
    'Content-Type': 'application/json'
}

for name, email, phone, token in restaurants:
    demo_url = f"http://localhost:8080/demo/{token}"
    
    body = f"""Hi there,

We noticed {name} doesn't have a website yet. In 2026, 87% of diners search online before choosing where to eat — and if they can't find you online, they go to your competitor.

I built a custom website for {name} — completely free to preview:

{demo_url}

Your site includes:
Full menu with photos
Click-to-call ordering button
Hours and location
Mobile-friendly design
SEO so customers find you on Google

All for just $299 one-time. Includes custom domain, hosting, and search engine listing.

This preview expires in 72 hours.

Reply to this email or call for questions.

Best,
M O
iconcre8tion@gmail.com"""

    payload = {
        'from': FROM,
        'to': [email],
        'reply_to': REPLY_TO,
        'subject': f'New website built for {name} — free preview',
        'text': body
    }
    
    try:
        resp = requests.post('https://api.resend.com/emails', headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            print(f'SENT: {name} -> {email}')
        else:
            print(f'FAILED: {name} -> {resp.status_code}: {resp.text[:100]}')
    except Exception as e:
        print(f'ERROR: {name} -> {e}')
