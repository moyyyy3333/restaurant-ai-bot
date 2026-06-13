"""Protected demo server — serves time-limited, copy-protected restaurant sites + webhooks"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory, abort, request, jsonify, render_template_string, redirect
from datetime import datetime
import db
import config

app = Flask(__name__)


# ── Existing endpoints ──

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200


@app.route("/")
def home():
    return jsonify({
        "status": "Restaurant AI Demo Server",
        "endpoints": {
            "/demo/<token>": "View protected restaurant demo",
            "/buy/<lead_id>": "Buy a site — $299",
            "/webhook/resend": "Incoming email reply webhook",
            "/webhook/twilio": "Incoming SMS reply webhook",
            "/webhook/stripe": "Stripe payment confirmation",
            "/health": "Health check"
        }
    })


@app.route("/demo/<token>")
def view_demo(token):
    """Serve a protected demo site by token"""
    site = db.get_demo_by_token(token)
    if not site:
        return render_template_string("""
        <!DOCTYPE html>
        <html><head><title>Not Found</title>
        <style>body{font-family:system-ui;background:#050505;color:#888;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;padding:20px}
        h1{font-weight:300;color:#fff;font-size:2rem} .small{font-size:0.85rem}</style>
        </head>
        <body>
        <div>
            <h1>Link not found</h1>
            <p class="small">This demo link is invalid or has expired.</p>
        </div>
        </body></html>
        """), 404

    lead = db.get_db().execute(
        "SELECT demo_expires_at, demo_viewed, sold FROM leads WHERE id = ?",
        (site["lead_id"],)
    ).fetchone()

    if lead and lead["demo_expires_at"]:
        try:
            expires = datetime.fromisoformat(lead["demo_expires_at"])
            if datetime.now() > expires and not lead["sold"]:
                return render_template_string("""
                <!DOCTYPE html>
                <html><head><title>Expired</title>
                <style>body{font-family:system-ui;background:#050505;color:#888;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;padding:20px}
                h1{font-weight:300;color:#f0c040;font-size:2rem} .small{font-size:0.85rem} .btn{display:inline-block;margin-top:20px;padding:12px 28px;background:#f0c040;color:#000;text-decoration:none;border-radius:8px;font-weight:600}</style>
                </head>
                <body>
                <div>
                    <h1>Demo Expired ✌️</h1>
                    <p class="small">This preview link has expired. Contact the owner to request a new one.</p>
                </div>
                </body></html>
                """), 410
        except ValueError:
            pass

    if lead:
        db.get_db().execute("UPDATE leads SET demo_viewed = 1 WHERE id = ?", (site["lead_id"],))
        db.get_db().commit()

    html = site["html_content"]

    # If sold, show a sold badge instead of DEMO watermark
    if lead and lead["sold"]:
        sold_badge = """
        <div style="position:fixed;top:0;left:0;right:0;z-index:9999;background:#22c55e;color:#fff;text-align:center;padding:6px;font-size:13px;font-weight:600;letter-spacing:0.5px;">
            ✅ LIVE SITE — {name}
        </div>
        <div style="height:32px"></div>
        """.replace("{name}", site.get("name", ""))
        html = sold_badge + html

    return render_template_string(html)


# ── Buy page ──

@app.route("/buy/<int:lead_id>")
def buy_page(lead_id):
    """Buy page shown after customer agrees to purchase"""
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        return "Lead not found", 404

    name = lead.get("name", "Restaurant")
    demo_token = lead.get("demo_token", "")
    demo_url = f"{config.DEMO_BASE_URL}/demo/{demo_token}" if demo_token else "#"

    return render_template_string("""
    <!DOCTYPE html>
    <html><head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Claim Your Site — {{ name }}</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e2e2e8;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
        .card{background:#12121a;border-radius:16px;border:1px solid #222;padding:40px;max-width:480px;width:100%;text-align:center}
        h1{font-size:1.8rem;margin-bottom:8px;color:#fff}
        .price{font-size:3rem;font-weight:800;color:#22d55e;margin:24px 0 8px}
        .price-label{color:#888;font-size:0.9rem;margin-bottom:24px}
        .features{text-align:left;margin:24px 0;padding:0;list-style:none}
        .features li{padding:10px 0;border-bottom:1px solid #1a1a24;font-size:0.95rem}
        .features li:last-child{border-bottom:0}
        .btn{display:inline-block;padding:16px 40px;background:#22d55e;color:#000!important;text-decoration:none;border-radius:12px;font-weight:700;font-size:1.1rem;margin:16px 0;transition:transform 0.2s;border:none;cursor:pointer}
        .btn:hover{transform:translateY(-2px)}
        .small{color:#555;font-size:0.8rem;margin-top:16px}
        .demo-link{color:#f0c040;text-decoration:none;font-size:0.9rem}
        .demo-link:hover{text-decoration:underline}
    </style>
    </head><body>
    <div class="card">
        <h1>{{ name }}</h1>
        <p style="color:#888;margin-bottom:8px">Claim your professional website</p>
        <div class="price">$299</div>
        <div class="price-label">One-time payment · Includes domain + hosting + SSL</div>
        <ul class="features">
            <li>✅ Custom domain (yourrestaurant.com)</li>
            <li>✅ Full menu with click-to-call ordering</li>
            <li>✅ Mobile-optimized design</li>
            <li>✅ Google Maps listing integration</li>
            <li>✅ Free SSL certificate</li>
            <li>✅ Lifetime hosting</li>
        </ul>
        <a class="btn" href="{{ stripe_url }}" target="_blank">💳 Pay $299 — Get Your Site Live</a>
        <br>
        <a class="demo-link" href="{{ demo_url }}" target="_blank">🔗 Still deciding? View your demo</a>
        <p class="small">Secure checkout via Stripe · 30-day satisfaction guarantee</p>
    </div>
    </body></html>
    """, name=name, demo_url=demo_url, stripe_url="#")


# ── Webhooks ──

@app.route("/webhook/resend", methods=["POST"])
def webhook_resend():
    """Resend incoming email webhook — detects customer replies"""
    data = request.get_json(silent=True) or {}
    
    # Resend sends: { email: 'sender@example.com', subject: '...', text: '...' }
    sender = data.get("email", "") or data.get("from", "")
    subject = data.get("subject", "")
    body_text = (data.get("text", "") or data.get("html", "") or "").lower()

    # Check for positive signal
    is_positive = any(word in body_text for word in ["yes", "interested", "let's do it", "i want", "claim", "purchase", "buy", "send link"])
    is_negative = any(word in body_text for word in ["stop", "no", "unsubscribe", "leave me alone", "not interested"])

    if is_negative:
        print(f"📧 Negative reply from {sender}")
        return jsonify({"status": "noted", "action": "none"}), 200

    if not is_positive:
        print(f"📧 Unclear reply from {sender}")
        return jsonify({"status": "noted", "action": "none"}), 200

    # Find lead by email
    lead = db.get_db().execute("""
        SELECT l.id, l.demo_token, r.name FROM leads l
        JOIN restaurants r ON l.restaurant_id = r.id
        WHERE l.email_replied = 0
        ORDER BY l.id DESC LIMIT 50
    """).fetchone()

    if not lead:
        print(f"📧 Positive reply from {sender} but no matching lead found")
        return jsonify({"status": "not_found"}), 200

    # Record the reply
    db.get_db().execute(
        "UPDATE leads SET email_replied = 1, followed_up = 1, status = 'interested' WHERE id = ?",
        (lead["id"],)
    )
    db.get_db().commit()

    print(f"💥 INTERESTED! Lead #{lead['id']} — {lead['name']} replied YES")

    # Trigger sale pipeline
    from pipeline import process_sale
    process_sale(lead["id"])

    return jsonify({"status": "processing", "lead_id": lead["id"], "name": lead["name"]}), 200


@app.route("/webhook/twilio", methods=["POST"])
def webhook_twilio():
    """Twilio incoming SMS webhook"""
    from_number = request.form.get("From", "")
    body = (request.form.get("Body", "") or "").strip().upper()

    if body in ("YES", "Y", "YES PLEASE", "INTERESTED", "YEAH", "YUP"):
        # Find lead by phone
        phone = from_number
        lead = db.get_db().execute("""
            SELECT l.id, l.demo_token, r.name FROM leads l
            JOIN restaurants r ON l.restaurant_id = r.id
            WHERE r.phone LIKE ? AND l.sold = 0
            ORDER BY l.id DESC LIMIT 1
        """, (f"%{phone[-10:]}",)).fetchone()

        if lead:
            db.get_db().execute(
                "UPDATE leads SET email_replied = 1, followed_up = 1, status = 'interested' WHERE id = ?",
                (lead["id"],)
            )
            db.get_db().commit()

            print(f"💥 SMS INTERESTED! Lead #{lead['id']} — {lead['name']}")
            from pipeline import process_sale
            process_sale(lead["id"])

    return "", 200


@app.route("/webhook/stripe", methods=["POST"])
def webhook_stripe():
    """Stripe payment confirmation webhook"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    # Verify webhook signature
    stripe_wh_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if stripe_wh_secret:
        import stripe
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, stripe_wh_secret)
        except ValueError:
            return jsonify({"error": "Invalid payload"}), 400
        except stripe.error.SignatureVerificationError:
            return jsonify({"error": "Invalid signature"}), 400
    else:
        event = json.loads(payload)

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        lead_id = int(session.get("metadata", {}).get("lead_id", 0))
        
        if lead_id:
            from pipeline import complete_sale
            complete_sale(lead_id, payment_id=session.get("id", ""),
                          customer_email=session.get("customer_details", {}).get("email", ""))
            print(f"💰 PAYMENT COMPLETED for lead #{lead_id}")

    return jsonify({"status": "ok"}), 200


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


if __name__ == "__main__":
    from config import DEMO_BASE_URL
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Restaurant AI Demo Server on port {port}")
    print(f"🔗 Demo base: {DEMO_BASE_URL}")
    app.run(host="0.0.0.0", port=port, debug=True)
