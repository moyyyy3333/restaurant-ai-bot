"""
Demo site generator.

One self-contained HTML file per business — no build step, no external assets,
so it renders instantly from the server or from disk. Category-aware copy comes
from config.BUSINESS_CATEGORIES.

Everything the business didn't give us is clearly marked as sample content, so
the demo never puts false claims (fake prices, fake hours) in a real business's
name.
"""

import html
import secrets
from datetime import datetime

from config import BUSINESS_CATEGORIES, PRICE_USD
from writer import write_copy

PALETTES = {
    "restaurant": ("#1a1410", "#e8b04b", "#f6f1e8"),
    "cafe":       ("#191512", "#c98a5b", "#f7f2ec"),
    "bakery":     ("#1d1712", "#d9a05b", "#fbf6ee"),
    "barber":     ("#0f1114", "#9fb4c7", "#f2f4f7"),
    "salon":      ("#16121a", "#d4a2c8", "#f8f3f7"),
    "auto":       ("#101215", "#e07c3c", "#f3f4f5"),
    "gym":        ("#0d0f11", "#7fd1a6", "#f1f5f3"),
    "florist":    ("#141810", "#a8c46a", "#f5f8ef"),
    "dentist":     ("#0f1417", "#6cc2c9", "#f1f6f6"),
    "lawyer":      ("#12130f", "#b89b5e", "#f6f5f0"),
    "plumber":     ("#0e1216", "#5b9bd5", "#f2f5f8"),
    "electrician": ("#131009", "#f2c14e", "#f8f6ee"),
    "roofer":      ("#111214", "#c0392b", "#f4f2f1"),
    "locksmith":   ("#121114", "#a89f6b", "#f5f4ef"),
    "jewelry":     ("#14100c", "#e0b354", "#f8f3e9"),
    "tattoo":      ("#0c0c0d", "#8a4fff", "#f2f0f6"),
    "veterinary":  ("#0f1512", "#6fbf8b", "#f1f6f2"),
    "optician":    ("#0f1216", "#5aa9c6", "#f2f5f7"),
    "dry_cleaning":("#111417", "#7ec8e3", "#f2f6f8"),
    "photo":       ("#0d0d0f", "#d1a1e0", "#f5f2f6"),
    "accountant":  ("#0f1113", "#4f9d69", "#f1f5f2"),
    "estate_agent":("#12100c", "#c98a3a", "#f7f3ec"),
    "insurance":   ("#0f1215", "#4a90d9", "#f1f4f8"),
    "pet":         ("#141210", "#e39b4e", "#f8f4ee"),
    "hardware":    ("#111112", "#d67d3e", "#f5f3f1"),
    "books":       ("#100f14", "#8f7bc4", "#f4f2f7"),
}

# Small, deliberate deltas per mood — not full alternate templates, just enough
# to make businesses in the same category not look like reskins of each other.
MOOD_STYLES = {
    "classic": dict(heading_font="Georgia,'Times New Roman',serif", h_align="center",
                     h_weight="400", radius_card="10px", radius_cta="6px", tag_ls=".32em"),
    "minimal": dict(heading_font="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif",
                     h_align="center", h_weight="300", radius_card="3px", radius_cta="3px", tag_ls=".4em"),
    "warm": dict(heading_font="Georgia,'Times New Roman',serif", h_align="left",
                 h_weight="500", radius_card="18px", radius_cta="999px", tag_ls=".2em"),
    "bold": dict(heading_font="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif",
                 h_align="center", h_weight="700", radius_card="2px", radius_cta="2px", tag_ls=".08em"),
}

SAMPLE = {
    "restaurant": [("House Specialty", "Ask about today's preparation"),
                   ("Family Platter", "Made for sharing"),
                   ("Daily Soup", "Changes with the season")],
    "cafe": [("Espresso", "Single or double"), ("Pour Over", "Rotating beans"),
             ("Fresh Pastry", "Baked each morning")],
    "bakery": [("Morning Breads", "Out of the oven by 7am"),
               ("Custom Cakes", "Order ahead"), ("Pastry Case", "Changes daily")],
    "barber": [("Haircut", "Classic or modern"), ("Beard Trim", "Hot towel finish"),
               ("Kids Cut", "Ages 12 and under")],
    "salon": [("Cut & Style", "Consultation included"), ("Color", "Full or partial"),
              ("Treatment", "Ask about options")],
    "auto": [("Diagnostics", "Know before you spend"), ("Brakes & Tires", "Same-day on most cars"),
             ("Oil Change", "While you wait")],
    "gym": [("Open Gym", "Free weights & machines"), ("Classes", "Check the schedule"),
            ("Personal Training", "First session intro")],
    "florist": [("Everyday Bouquet", "Designer's choice"), ("Events", "Consultation available"),
                ("Same-Day Delivery", "Order by noon")],
    "dentist": [("Cleanings", "Every six months"), ("Whitening", "In-office or take-home"),
                ("Emergency Care", "Same-day appointments")],
    "lawyer": [("Consultation", "Ask about your case"), ("Representation", "By practice area"),
               ("Documents", "Review and preparation")],
    "plumber": [("Repairs", "Leaks, clogs, and more"), ("Water Heaters", "Install and repair"),
                ("Emergency Service", "Available on call")],
    "electrician": [("Repairs", "Diagnose and fix"), ("Panel Upgrades", "Bring it up to code"),
                     ("New Installs", "Fixtures and wiring")],
    "roofer": [("Repairs", "Leaks and storm damage"), ("Replacement", "Full tear-off and install"),
               ("Inspection", "Free estimate")],
    "locksmith": [("Lockouts", "Home, auto, business"), ("Rekeying", "Same-day service"),
                  ("New Locks", "Installed on the spot")],
    "jewelry": [("Custom Pieces", "Designed with you"), ("Repairs", "Sizing and fixes"),
                ("Appraisals", "By appointment")],
    "tattoo": [("Custom Work", "Your design or ours"), ("Flash", "Walk-ins welcome"),
               ("Touch-Ups", "Ask about our policy")],
    "veterinary": [("Wellness Exams", "Yearly checkups"), ("Vaccinations", "Keep them protected"),
                    ("Urgent Care", "Call ahead")],
    "optician": [("Eye Exams", "By appointment"), ("Frames", "Wide selection in stock"),
                 ("Contacts", "Fitting included")],
    "dry_cleaning": [("Dry Cleaning", "Ready in 2 days"), ("Alterations", "While you wait"),
                      ("Wash & Fold", "Drop off anytime")],
    "photo": [("Portraits", "Studio or on location"), ("Events", "Full coverage"),
              ("Prints", "Same-week turnaround")],
    "accountant": [("Bookkeeping", "Monthly or quarterly"), ("Tax Prep", "Individual and business"),
                   ("Consulting", "By appointment")],
    "estate_agent": [("Buying", "Guided every step"), ("Selling", "Priced to move"),
                      ("Rentals", "Ask about availability")],
    "insurance": [("Auto", "Free quote"), ("Home", "Bundle and save"),
                  ("Life", "Talk to an agent")],
    "pet": [("Food & Supplies", "In stock"), ("Grooming", "By appointment"),
            ("Advice", "Ask our staff")],
    "hardware": [("Tools", "For every job"), ("Paint", "Custom mixed"),
                 ("Key Cutting", "While you wait")],
    "books": [("New Releases", "Restocked weekly"), ("Used & Rare", "Always changing"),
              ("Events", "Readings and signings")],
}


def generate_site(name, address="", phone="", category="restaurant", rating=None,
                  city="", lead_id=None, business_id=None, watermark=True):
    """Returns (html_string, token)."""
    token = secrets.token_urlsafe(9)
    cat = category if category in BUSINESS_CATEGORIES else "restaurant"
    meta = BUSINESS_CATEGORIES[cat]
    dark, accent, light = PALETTES.get(cat, PALETTES["restaurant"])

    e = lambda s: html.escape(str(s or ""))
    name_s, addr_s, phone_s = e(name), e(address), e(phone)
    tel = "".join(ch for ch in str(phone or "") if ch.isdigit())
    rating_html = ""
    if rating:
        stars = "★" * int(round(float(rating))) + "☆" * (5 - int(round(float(rating))))
        rating_html = (f'<div class="rating"><span class="stars">{stars}</span>'
                       f'<span class="rnum">{float(rating):.1f} on Google</span></div>')

    ai = write_copy(name, meta["label"], city)
    hero = ai["tagline"] if ai and ai["tagline"] else meta["hero"]
    items = ai["items"] if ai else SAMPLE.get(cat, SAMPLE["restaurant"])
    if ai and ai["accent"]:
        accent = ai["accent"]
    m = MOOD_STYLES[ai["mood"]] if ai and ai["mood"] else MOOD_STYLES["classic"]
    cards = "".join(
        f'<div class="card"><h3>{e(t)}</h3><p>{e(d)}</p></div>'
        for t, d in items)

    mark = ""
    if watermark:
        mark = ('<div class="wm">PREVIEW</div>'
                '<div class="claimbar">This is a free sample site built for '
                f'{name_s}. Nothing is published. '
                f'<a href="#claim">See how to claim it</a></div>')

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{name_s}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
background:{light};color:{dark};line-height:1.6}}
.wm{{position:fixed;top:14px;right:14px;background:{dark};color:{accent};
padding:6px 14px;border-radius:99px;font-size:11px;letter-spacing:.2em;z-index:99;opacity:.9}}
.claimbar{{background:{dark};color:{light};text-align:center;padding:10px 16px;font-size:13.5px}}
.claimbar a{{color:{accent}}}
header{{background:{dark};color:{light};padding:88px 24px 76px;text-align:{m['h_align']}}}
header h1{{font-size:clamp(32px,6vw,58px);font-weight:{m['h_weight']};letter-spacing:.02em;
font-family:{m['heading_font']}}}
.tag{{color:{accent};letter-spacing:{m['tag_ls']};text-transform:uppercase;font-size:12px;margin-bottom:20px}}
.hero{{color:{light};opacity:.82;margin-top:16px;font-size:18px}}
.rating{{margin-top:22px;font-size:14px;color:{light};opacity:.9}}
.stars{{color:{accent};letter-spacing:2px;margin-right:8px}}
.cta{{display:inline-block;margin-top:30px;background:{accent};color:{dark};
padding:14px 34px;border-radius:{m['radius_cta']};text-decoration:none;font-weight:600;font-size:15px}}
section{{max-width:940px;margin:0 auto;padding:64px 24px}}
h2{{font-size:26px;font-weight:{m['h_weight']};margin-bottom:8px;font-family:{m['heading_font']}}}
.sub{{color:#6b6b6b;font-size:14px;margin-bottom:28px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}}
.card{{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:{m['radius_card']};padding:22px}}
.card h3{{font-size:17px;margin-bottom:6px}}
.card p{{color:#6b6b6b;font-size:14px}}
.info{{background:#fff;border-top:1px solid rgba(0,0,0,.07)}}
.inforow{{display:flex;flex-wrap:wrap;gap:36px;max-width:940px;margin:0 auto;padding:44px 24px}}
.inforow div{{flex:1;min-width:200px}}
.inforow b{{display:block;font-size:12px;letter-spacing:.16em;text-transform:uppercase;
color:{accent};margin-bottom:8px}}
#claim{{background:{dark};color:{light}}}
#claim .box{{max-width:720px;margin:0 auto;padding:64px 24px;text-align:center}}
#claim h2{{color:{light}}}
#claim p{{opacity:.8;margin-bottom:22px}}
.note{{font-size:12.5px;color:#8a8a8a;text-align:center;padding:0 24px 40px}}
footer{{background:{dark};color:{light};opacity:.75;text-align:center;padding:26px;font-size:12.5px}}
</style></head><body>
{mark}
<header>
  <div class="tag">{e(meta['label'])}{(' · ' + e(city.title())) if city else ''}</div>
  <h1>{name_s}</h1>
  <p class="hero">{e(hero)}</p>
  {rating_html}
  {f'<a class="cta" href="tel:{tel}">Call {phone_s}</a>' if tel else ''}
</header>

<section>
  <h2>{e(meta['sections'][0])}</h2>
  <p class="sub">Sample layout — your real items and prices go here.</p>
  <div class="grid">{cards}</div>
</section>

<div class="info"><div class="inforow">
  <div><b>Find us</b>{addr_s or 'Your address here'}</div>
  <div><b>Call</b>{phone_s or 'Your phone here'}</div>
  <div><b>Hours</b>Add your real hours — this line is a placeholder.</div>
</div></div>

<section id="claim"><div class="box">
  <h2>Want this as your real website?</h2>
  <p>This sample was built for {name_s} at no cost and nothing is published.
     If you want it live on your own domain — with your real menu, hours and photos —
     reply to the email that brought you here.</p>
  <p style="opacity:.95"><b>One-time setup: ${PRICE_USD}.</b> No subscription.
     If you'd rather not hear from us again, every email has a one-click opt-out.</p>
</div></section>

<p class="note">Sample content is marked as such. Business name, address, phone and rating
come from public Google Places data. Not affiliated with or endorsed by {name_s}.</p>

<footer>Preview generated {datetime.now().strftime('%B %d, %Y')} · ref {token}</footer>
</body></html>""", token


if __name__ == "__main__":
    h, t = generate_site("Taqueria La Esquina", "1234 Navigation Blvd, Houston, TX",
                         "(713) 555-0142", "restaurant", 4.6, "houston", 1, 1)
    from pathlib import Path
    p = Path(__file__).parent / "demos" / f"sample-{t}.html"
    p.parent.mkdir(exist_ok=True)
    p.write_text(h)
    print(f"wrote {p}")
