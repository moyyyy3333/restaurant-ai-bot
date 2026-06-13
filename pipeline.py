"""
Restaurant AI Bot — Autonomous Pipeline
Runs on cron to automate: scan → generate → email → follow-up → domain provisioning
"""
import sys, os, time, json, requests
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import db
from scanner.scanner import scan_area_houston
from generator import generate_with_sample_menu
from config import (
    DEMO_BASE_URL, DEMO_EXPIRE_HOURS, HOUSTON_AREAS,
    RESEND_API_KEY, FROM_EMAIL, USE_TWILIO
)

STAGE = os.environ.get("RAILWAY_ENVIRONMENT", "production")


# ── Stage 1: Scan ──

def auto_scan():
    """Scan next unscanned area. Returns leads found."""
    scanned_areas = set()
    for row in db.get_db().execute("SELECT DISTINCT area FROM scan_log").fetchall():
        scanned_areas.add(row["area"])

    remaining = [a for a in HOUSTON_AREAS if a not in scanned_areas]
    if not remaining:
        print("✅ All areas already scanned. Re-scanning oldest...")
        target = HOUSTON_AREAS[0]  # re-scan first area
    else:
        target = remaining[0]

    print(f"🔍 Scanning: {target}")
    leads = scan_area_houston(target)
    print(f"  → {leads} new leads from {target}")
    return leads, target


def auto_scan_all_remaining():
    """Scan all remaining unscanned areas. Run once for initial fill."""
    total = 0
    scanned_areas = set()
    for row in db.get_db().execute("SELECT DISTINCT area FROM scan_log").fetchall():
        scanned_areas.add(row["area"])

    for area in HOUSTON_AREAS:
        if area in scanned_areas:
            continue
        leads = scan_area_houston(area)
        total += leads
        time.sleep(2)

    print(f"🏁 Initial scan complete: {total} new leads")
    return total


# ── Stage 2: Generate ──

def auto_generate(limit=5):
    """Generate sites for leads that don't have one yet."""
    leads = db.get_db().execute("""
        SELECT l.id, r.id as restaurant_id, r.name, r.address, r.phone, r.cuisine, r.rating
        FROM leads l
        JOIN restaurants r ON l.restaurant_id = r.id
        WHERE l.demo_token IS NULL AND l.sold = 0
        ORDER BY l.priority DESC, l.id ASC
        LIMIT ?
    """, (limit,)).fetchall()

    generated = 0
    for lead in leads:
        name = lead["name"]
        print(f"🖥️ Generating site for {name}...")

        html_content, token = generate_with_sample_menu(
            name=name,
            address=lead["address"] or "",
            phone=lead["phone"] or "",
            cuisine=lead.get("cuisine") or "",
            rating=lead.get("rating"),
            lead_id=lead["id"],
            restaurant_id=lead["restaurant_id"]
        )

        db.create_demo_site(lead["id"], lead["restaurant_id"], html_content, token)

        expires_at = datetime.now() + timedelta(hours=DEMO_EXPIRE_HOURS)
        db.update_lead(
            lead["id"],
            status="site_generated",
            demo_token=token,
            demo_created_at=datetime.now().isoformat(),
            demo_expires_at=expires_at.isoformat()
        )

        print(f"  ✅ Generated — token: {token}")
        generated += 1

    print(f"🏁 Generated {generated} new sites")
    return generated


# ── Stage 3: Email ──

def auto_email(limit=5):
    """Send outreach emails for leads with sites but no contact yet."""
    leads = db.get_db().execute("""
        SELECT l.id, l.demo_token, r.name
        FROM leads l
        JOIN restaurants r ON l.restaurant_id = r.id
        WHERE l.demo_token IS NOT NULL
          AND l.emailed = 0
          AND l.sold = 0
        ORDER BY l.priority DESC, l.id ASC
        LIMIT ?
    """, (limit,)).fetchall()

    if not RESEND_API_KEY:
        print("⚠️ No RESEND_API_KEY — skipping email")
        return 0

    sent = 0
    for lead in leads:
        name = lead["name"]
        demo_url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"

        print(f"📧 Emailing {name}...")

        # Try to find email (from Google Places or generated)
        rest = db.get_db().execute(
            "SELECT phone, address FROM restaurants WHERE id = (SELECT restaurant_id FROM leads WHERE id = ?)",
            (lead["id"],)
        ).fetchone()

        # Use Resend
        payload = {
            "from": f"Neo @ Restaurant AI <{FROM_EMAIL}>",
            "to": [f"placeholder@restaurant.ai"],  # Will be replaced when we find real emails
            "subject": f"Your new {name} website is ready — free preview",
            "html": _build_email_html(name, demo_url),
        }

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=15
            )
            if resp.status_code == 200:
                email_id = resp.json().get("id", "?")
                db.update_lead(lead["id"], emailed=1, status="emailed",
                               email_sent_at=datetime.now().isoformat())
                print(f"  ✅ Sent — ID: {email_id}")
                sent += 1
            else:
                print(f"  ❌ Resend error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  ❌ Email error: {e}")

    print(f"🏁 Emailed {sent} leads")
    return sent


def _build_email_html(name, demo_url):
    return f"""<!DOCTYPE html>
<html><head><style>
body{{font-family:-apple-system,sans-serif;background:#fafafa;padding:40px 20px}}
.container{{max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 2px 20px rgba(0,0,0,0.06)}}
h1{{font-size:22px;font-weight:600;color:#1a1a1a}}
p{{font-size:15px;line-height:1.6;color:#555;margin-bottom:20px}}
.restaurant-name{{font-size:20px;font-weight:700;color:#f0c040}}
.preview-btn{{display:inline-block;padding:14px 32px;background:#1a1a1a;color:#fff!important;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;margin:10px 0}}
.features{{background:#f8f8f5;border-radius:8px;padding:20px;margin:20px 0;list-style:none}}
.features li{{font-size:14px;color:#444;padding:6px 0;border-bottom:1px solid #eee}}
.features li:last-child{{border-bottom:0}}
.invoice{{background:#fff8e1;border:1px solid #f0c040;border-radius:8px;padding:16px 20px;margin:16px 0}}
.invoice-amount{{font-size:24px;font-weight:700;color:#1a1a1a}}
.small{{font-size:12px;color:#aaa;margin-top:24px}}
hr{{border:0;border-top:1px solid #eee;margin:24px 0}}
</style></head><body>
<div class="container">
<h1>Hi there,</h1>
<p>We built a modern website for <span class="restaurant-name">{name}</span> — completely free to preview.</p>
<ul class="features">
<li>📱 Mobile-optimized design</li>
<li>📞 Click-to-call ordering button</li>
<li>🍽️ Full menu display</li>
<li>📍 Hours, location, contact</li>
<li>🔍 Google / SEO ready</li>
</ul>
<p style="text-align:center"><a href="{demo_url}" class="preview-btn">Preview Your Site →</a></p>
<div class="invoice">
<strong style="display:block;color:#1a1a1a;font-size:13px">One-Time Setup</strong>
<div class="invoice-amount">$299</div>
<div style="font-size:13px;color:#666;margin-top:4px">Includes hosting + domain + updates</div>
</div>
<p style="font-size:14px;color:#666">Reply YES to this email to claim your site.</p>
<hr>
<p class="small">Built by AI · Houston, TX<br>Reply STOP to opt out.</p>
</div></body></html>"""


# ── Stage 4: Sale Processing ──

def process_sale(lead_id):
    """Customer replied YES — mark interested and send Stripe payment link."""
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        print(f"❌ process_sale: lead #{lead_id} not found")
        return

    name = lead.get("name", "Restaurant")
    demo_token = lead.get("demo_token", "")
    buy_url = f"{DEMO_BASE_URL}/buy/{lead_id}"

    db.update_lead(lead_id, status="interested", followed_up=1)

    print(f"""
💥 === SALE PROCESSING ===
  Lead #{lead_id}: {name}
  Status: interested
  Buy page: {buy_url}
  Demo: {DEMO_BASE_URL}/demo/{demo_token}

  ▶ Action needed: Customer agreed to buy!
  ▶ Send buy link: {buy_url}
  ▶ After payment → domain provisioning
""")


def complete_sale(lead_id, payment_id, customer_email):
    """Payment confirmed — provision domain and make site live."""
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        print(f"❌ complete_sale: lead #{lead_id} not found")
        return

    name = lead.get("name", "Restaurant")

    # 1. Mark as sold
    db.update_lead(lead_id, sold=1, status="sold",
                   sold_at=datetime.now().isoformat())

    # 2. Log payment
    db.get_db().execute(
        "INSERT INTO email_log (lead_id, to_email, subject, replied) VALUES (?, ?, ?, 1)",
        (lead_id, customer_email, f"Payment completed — {name}")
    )
    db.get_db().commit()

    # 3. Provision domain (Phase 2 — placeholder for now)
    domain_name = _generate_domain_name(name)

    print(f"""
💰 === SALE COMPLETED ===
  Lead #{lead_id}: {name}
  Payment: {payment_id}
  Customer: {customer_email}
  Suggested domain: {domain_name}

  ✅ Sale recorded — $299
  ▶ Phase 2: Auto-provision domain {domain_name}
  ▶ Phase 2: Deploy live site
""")


def _generate_domain_name(restaurant_name):
    """Generate a domain name suggestion from restaurant name."""
    name = restaurant_name.lower()
    name = name.replace("'", "").replace("&", "and")
    name = name.replace("(", "").replace(")", "")
    name = name.replace(",", "")
    # Take first 2 meaningful words
    words = [w for w in name.split() if w not in ("the", "a", "an", "of", "in", "and")]
    if not words:
        words = name.split()
    slug = "-".join(words[:3])[:40]
    slug = slug.strip("-")
    return f"{slug}.com"


# ── Main pipeline ──

def run_pipeline():
    """Run one cycle of the full automation pipeline."""
    print(f"\n{'='*50}")
    print(f"🤖 Pipeline Run — {datetime.now().isoformat()}")
    print(f"{'='*50}\n")

    # Stage 1: Scan
    leads_found, area = auto_scan()

    # Stage 2: Generate (for any new leads)
    generated = auto_generate(limit=5)

    # Stage 3: Email (for newly generated sites)
    emailed = auto_email(limit=5)

    # Summary
    stats = db.get_stats()
    print(f"\n{'='*50}")
    print(f"📊 Pipeline Summary")
    print(f"  Scanned: {area} → {leads_found} leads")
    print(f"  Generated: {generated} sites")
    print(f"  Emailed: {emailed}")
    print(f"  Total: {stats['restaurants']} restaurants, {stats['leads']} leads, {stats['sold']} sold")
    print(f"{'='*50}\n")

    return {
        "leads_found": leads_found,
        "generated": generated,
        "emailed": emailed,
        "total_restaurants": stats["restaurants"],
        "total_leads": stats["leads"],
        "total_sold": stats["sold"],
    }


if __name__ == "__main__":
    run_pipeline()
