"""Email outreach via Resend or Gmail SMTP"""
import requests
import json
import smtplib
from email.mime.text import MIMEText
from config import RESEND_API_KEY, FROM_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS

RESEND_URL = "https://api.resend.com/emails"

def send_outreach(owner_name, restaurant_name, demo_url, owner_email=None):
    """
    Send outreach email to restaurant owner.
    Tries Resend first, falls back to SMTP.
    """
    subject = f"Your new {restaurant_name} website is ready"
    
    html_content = _build_html(owner_name, restaurant_name, demo_url)
    
    # Try Resend first
    if RESEND_API_KEY:
        result = _send_resend(owner_email or "placeholder@restaurant.ai", subject, html_content, restaurant_name)
        if result:
            return result
    
    # Fall back to SMTP
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        result = _send_smtp(owner_email or "placeholder@restaurant.ai", subject, html_content, restaurant_name)
        if result:
            return result
    
    print(f"⚠️  No email method available for {restaurant_name}")
    return None


def _send_resend(to_email, subject, html, restaurant_name):
    """Send via Resend API"""
    payload = {
        "from": f"Neo @ Restaurant AI <{FROM_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    try:
        resp = requests.post(RESEND_URL, headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }, json=payload, timeout=15)
        if resp.status_code == 200:
            email_id = resp.json().get('id', '?')
            print(f"  ✅ Via Resend — ID: {email_id}")
            return {"method": "resend", "id": email_id}
        else:
            print(f"  ❌ Resend error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  ❌ Resend error: {e}")
        return None


def _send_smtp(to_email, subject, html, restaurant_name):
    """Send via SMTP (Gmail, etc.)"""
    try:
        msg = MIMEText(html, 'html')
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"  ✅ Via SMTP — {to_email}")
        return {"method": "smtp", "to": to_email}
    except Exception as e:
        print(f"  ❌ SMTP error: {e}")
        return None


def _build_html(owner_name, restaurant_name, demo_url):
    """Build outreach email HTML"""
    return f"""
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
            .invoice {{ background: #fff8e1; border: 1px solid #f0c040; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }}
            .invoice-amount {{ font-size: 24px; font-weight: 700; color: #1a1a1a; }}
            .small {{ font-size: 12px; color: #aaa; margin-top: 24px; }}
            hr {{ border: 0; border-top: 1px solid #eee; margin: 24px 0; }}
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
            <p style="font-size:14px;color:#666">The preview link expires in 72 hours. Reply to this email to claim your site.</p>
            <hr>
            <p class="small">Built by AI · Houston, TX</p>
        </div>
    </body>
    </html>
    """

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
