"""Email outreach via Resend API"""
import requests
import json
from config import RESEND_API_KEY, FROM_EMAIL

RESEND_URL = "https://api.resend.com/emails"

def send_outreach(owner_name, restaurant_name, demo_url, owner_email=None):
    """
    Send outreach email to restaurant owner.
    If owner_email is not known, uses a generic approach.
    """
    if not RESEND_API_KEY:
        print("⚠️  No Resend API key — email sending disabled")
        return None
    
    subject = f"Your new {restaurant_name} website is ready"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #fafafa; padding: 40px 20px; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 20px rgba(0,0,0,0.06); }}
            h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 8px; color: #1a1a1a; }}
            p {{ font-size: 15px; line-height: 1.6; color: #555; margin-bottom: 20px; }}
            .restaurant-name {{ font-size: 20px; font-weight: 700; color: #f0c040; margin-bottom: 20px; }}
            .preview-btn {{ display: inline-block; padding: 14px 32px; background: #1a1a1a; color: #fff !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; margin: 10px 0; }}
            .features {{ background: #f8f8f5; border-radius: 8px; padding: 20px; margin: 20px 0; }}
            .features li {{ font-size: 14px; color: #444; padding: 6px 0; border-bottom: 1px solid #eee; }}
            .features li:last-child {{ border-bottom: 0; }}
            .small {{ font-size: 12px; color: #aaa; margin-top: 24px; }}
            hr {{ border: 0; border-top: 1px solid #eee; margin: 24px 0; }}
            .invoice {{ background: #fff8e1; border: 1px solid #f0c040; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }}
            .invoice-amount {{ font-size: 24px; font-weight: 700; color: #1a1a1a; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Hi {owner_name or 'there'},</h1>
            <p>We built a modern website for <span class="restaurant-name">{restaurant_name}</span> — completely free to preview.</p>
            
            <div class="features">
                <strong style="display:block;margin-bottom:8px;color:#1a1a1a">Includes:</strong>
                <ul style="list-style:none;padding:0;margin:0">
                    <li>📱 Mobile-optimized design</li>
                    <li>📞 Click-to-call ordering button</li>
                    <li>🍽️ Full menu display</li>
                    <li>📍 Hours, location, contact</li>
                    <li>🔍 Google Maps / SEO ready</li>
                </ul>
            </div>
            
            <p style="text-align:center">
                <a href="{demo_url}" class="preview-btn">Preview Your Site →</a>
            </p>
            
            <div class="invoice">
                <strong style="display:block;color:#1a1a1a;font-size:13px">One-Time Setup</strong>
                <div class="invoice-amount">$299</div>
                <div style="font-size:13px;color:#666;margin-top:4px">Includes hosting + domain + updates</div>
            </div>
            
            <p style="font-size:14px;color:#666">
                The preview link expires in 72 hours. Reply to this email to claim your site or ask questions.
            </p>
            
            <hr>
            <p class="small">
                Built by AI · Houston, TX<br>
                If you'd rather not receive emails, reply "stop" and we'll leave you alone.
            </p>
        </div>
    </body>
    </html>
    """
    
    payload = {
        "from": f"Neo @ Restaurant AI <{FROM_EMAIL}>",
        "to": [owner_email] if owner_email else ["placeholder@restaurant.ai"],
        "subject": subject,
        "html": html_content,
    }
    
    try:
        resp = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )
        result = resp.json()
        if resp.status_code == 200:
            print(f"✅ Email sent for {restaurant_name} — ID: {result.get('id', '?')}")
            return result
        else:
            print(f"❌ Email failed: {resp.status_code} — {result}")
            return None
    except Exception as e:
        print(f"❌ Email error: {e}")
        return None

def build_generic_email(restaurant_name):
    """Find a common email format for a restaurant"""
    name_clean = restaurant_name.lower().replace("'", "").replace("&", "and")
    name_slug = name_clean.replace(" ", "")
    
    # Common formats
    formats = [
        f"info@{name_slug}.com",
        f"{name_slug}houston@gmail.com",
        f"{name_slug}tx@gmail.com",
        f"contact@{name_slug}.com",
    ]
    return formats
