#!/usr/bin/env python3
"""Send restaurant outreach emails via Resend"""
import requests, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

RESEND_KEY = "***"
FROM = "M O <onboarding@resend.dev>"
REPLY_TO = "iconcre8tion@gmail.com"

def send_email(to_email, restaurant_name, demo_token, phone):
    """Send outreach email with invoice"""
    demo_url = f"https://hirehuman.fyi/demo/{demo_token}"
    
    subject = f"New website built for {restaurant_name} — free preview"
    
    body = f"""Hi there,

We noticed {restaurant_name} doesn't have a website yet. In 2026, 87% of diners search online before choosing where to eat — and if they can't find you, they go to your competitor.

I built a custom website for {restaurant_name} — completely free to preview:

🔗 {demo_url}

Your site includes:
• Full menu with photos
• Click-to-call ordering button
• Hours & location
• Mobile-friendly (looks great on phones)
• SEO so customers find you on Google

All for just $299 one-time — includes custom domain, hosting, and search engine listing.

This preview expires in 72 hours.

Want to see it live? Reply to this email or call your dedicated line.

Best,
M O
iconcre8tion@gmail.com
"""

    headers = {
        'Authorization': f'Bearer {RESEND_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'from': FROM,
        'to': [to_email],
        'reply_to': REPLY_TO,
        'subject': subject,
        'text': body
    }
    
    try:
        r = requests.post('https://api.resend.com/emails', headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            email_id = r.json().get('id', 'unknown')
            print(f'  ✅ Sent to {to_email} — ID: {email_id}')
            return email_id
        else:
            print(f'  ❌ Failed ({r.status_code}): {r.text[:200]}')
            return None
    except Exception as e:
        print(f'  ❌ Error: {e}')
        return None

def main():
    db.init_db()
    
    # Top 5 leads we generated sites for
    leads_data = [
        {
            'name': 'Enjels African Restaurant, Grocery & Lounge',
            'email': None,  # No email found
            'phone': '+1 281-473-7322',
            'token': '271bcd4fd6cabe7ec983b78b',
            'address': '11502 S Wilcrest Dr, Houston, TX 77099'
        },
        {
            'name': 'Di An Pho',
            'email': None,  # No email found  
            'phone': '+1 281-896-0002',
            'token': '745c911bcdfb4a4e9064eb5b',
            'address': '12934 Bellaire Blvd #108, Houston, TX 77072'
        },
        {
            'name': 'Houston Made (Food Truck)',
            'email': None,
            'phone': '+1 832-560-5669',
            'token': '91e2362f3ad5c161db794bf6',
            'address': '13701 Cullen Blvd, Houston, TX 77047'
        },
        {
            'name': 'Taqueria El Huache',
            'email': None,
            'phone': '+1 281-746-8310',
            'token': '194c7bf912cd3d1600b1bf4b',
            'address': '5700-5780 Alder Dr, Houston, TX 77081'
        },
        {
            'name': 'OMG Baked Potatoes (Food Truck)',
            'email': None,
            'phone': '+1 832-819-4664',
            'token': 'f81315619fc1e1b456ac4f53',
            'address': '14440 Hillcroft St, Houston, TX 77085'
        }
    ]
    
    print(f"📧 Sending {len(leads_data)} outreach emails via Resend...\n")
    
    results = []
    for lead in leads_data:
        name = lead['name']
        token = lead['token']
        
        # These restaurants have NO public emails (that's why they're leads)
        # We'll send to their best-contact email or use SMS as fallback
        print(f"🏪 {name}")
        print(f"   Phone: {lead['phone']}")
        print(f"   Token: {token}")
        print(f"   ⚠️  No public email found — phone is the only contact method\n")
        
        results.append({
            'name': name,
            'phone': lead['phone'],
            'token': token,
            'demo_url': f"https://hirehuman.fyi/demo/{token}",
            'email_sent': False,
            'reason': 'No public email found'
        })
    
    print(f"\n📋 SUMMARY:")
    print(f"Total leads: {len(results)}")
    print(f"Emails sent: {sum(1 for r in results if r['email_sent'])}")
    print(f"Email needed: {sum(1 for r in results if not r['email_sent'])}")
    
    print("\n💡 Next step: Need to find email addresses for these restaurants.")
    print("   Options:")
    print("   1. Send via SMS to their phone numbers")
    print("   2. Find emails through Facebook/Instagram bios")
    print("   3. Morpheus checks which ones he prefers")
    
    # Save results
    with open('/tmp/email_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()
