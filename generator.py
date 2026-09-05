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
import json
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
                  city="", lead_id=None, business_id=None, watermark=True, use_ai=True):
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

    ai = write_copy(name, meta["label"], city) if use_ai else None
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

    map_html = ""
    if address:
        map_q = html.escape(str(address), quote=True)
        map_html = (f'<iframe class="map" loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
                    f'src="https://maps.google.com/maps?q={map_q}&output=embed"></iframe>')

    desc = e(hero)[:150]
    sec0 = e(meta["sections"][0])
    year = datetime.now().year

    # Menu as an editorial list, not a card grid. No invented prices — the page
    # says plainly that real items and prices go in.
    menu_html = "".join(
        f'''<li class="item">
      <div class="item-h"><h3>{e(t)}</h3><span class="dots" aria-hidden="true"></span></div>
      <p>{e(d)}</p>
    </li>''' for t, d in items)

    # Machine-readable business record so search engines and assistants can use it.
    ld = {
        "@context": "https://schema.org", "@type": "LocalBusiness",
        "name": str(name), "description": str(hero),
    }
    if address: ld["address"] = str(address)
    if phone: ld["telephone"] = str(phone)
    if rating: ld["aggregateRating"] = {"@type": "AggregateRating",
                                        "ratingValue": float(rating), "bestRating": 5}
    ld_json = json.dumps(ld)

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="{dark}">
<meta name="description" content="{desc}">
<meta property="og:title" content="{name_s}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<title>{name_s}{(' · ' + e(city.title())) if city else ''}</title>
<script type="application/ld+json">{ld_json}</script>
<style>
:root{{
  --ink:{dark}; --accent:{accent}; --surface:{light};
  --paper:#fff; --muted:color-mix(in srgb, {dark} 55%, {light});
  --line:color-mix(in srgb, {dark} 14%, {light});
  --step--1:clamp(.82rem,.79rem + .14vw,.9rem);
  --step-0:clamp(1rem,.96rem + .2vw,1.1rem);
  --step-1:clamp(1.28rem,1.18rem + .5vw,1.6rem);
  --step-2:clamp(1.6rem,1.4rem + 1vw,2.3rem);
  --step-3:clamp(2.2rem,1.7rem + 2.6vw,4.2rem);
  --gap:clamp(1.4rem,1rem + 2vw,3rem);
  --rc:{m['radius_card']}; --rb:{m['radius_cta']};
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
@media (prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}
  *{{animation:none!important;transition:none!important}}}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif;
  background:var(--surface);color:var(--ink);font-size:var(--step-0);line-height:1.6;
  -webkit-font-smoothing:antialiased}}
h1,h2,h3{{font-family:{m['heading_font']};font-weight:{m['h_weight']};line-height:1.1;
  letter-spacing:-.01em;text-wrap:balance}}
a{{color:inherit}}
:focus-visible{{outline:3px solid var(--accent);outline-offset:3px;border-radius:2px}}
.skip{{position:absolute;left:-9999px}}
.skip:focus{{left:12px;top:12px;z-index:200;background:var(--ink);color:var(--surface);
  padding:10px 16px;border-radius:var(--rb)}}
.wrap{{max-width:1080px;margin:0 auto;padding-inline:clamp(20px,5vw,40px)}}
.wm{{position:fixed;top:14px;right:14px;background:var(--ink);color:var(--accent);
  padding:6px 14px;border-radius:99px;font-size:11px;letter-spacing:.2em;z-index:99}}
.claimbar{{background:var(--ink);color:var(--surface);text-align:center;
  padding:10px 16px;font-size:var(--step--1)}}
.claimbar a{{color:var(--accent)}}
nav{{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--surface) 88%,transparent);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
nav .wrap{{display:flex;align-items:center;justify-content:space-between;
  gap:1rem;padding-block:14px}}
nav .brand{{font-family:{m['heading_font']};font-weight:600;font-size:var(--step-0)}}
nav ul{{display:flex;align-items:center;gap:clamp(14px,2.4vw,28px);list-style:none}}
nav a{{text-decoration:none;font-size:var(--step--1);color:var(--muted)}}
nav a:hover{{color:var(--ink)}}
.btn{{display:inline-block;background:var(--accent);color:var(--ink);font-weight:650;
  padding:.7em 1.3em;border-radius:var(--rb);text-decoration:none;
  border:1px solid transparent;transition:filter .15s ease}}
.btn:hover{{filter:brightness(1.07)}}
.btn.ghost{{background:transparent;border-color:var(--line);color:var(--ink)}}
/* asymmetric editorial hero */
header{{padding-block:clamp(3.5rem,9vw,7rem) clamp(2.5rem,6vw,4.5rem);
  border-bottom:1px solid var(--line)}}
header .grid{{display:grid;grid-template-columns:1fr;gap:var(--gap);align-items:end}}
@media(min-width:820px){{header .grid{{grid-template-columns:1.35fr .65fr}}}}
.eyebrow{{font-size:var(--step--1);letter-spacing:{m['tag_ls']};text-transform:uppercase;
  color:var(--accent);font-weight:600;margin-bottom:1rem}}
h1{{font-size:var(--step-3);margin-bottom:1rem}}
.lede{{font-size:var(--step-1);color:var(--muted);max-width:34ch;line-height:1.35}}
.actions{{display:flex;flex-wrap:wrap;gap:12px;margin-top:2rem}}
.facts{{display:grid;gap:1.1rem;border-left:2px solid var(--accent);padding-left:1.2rem}}
.facts dt{{font-size:var(--step--1);letter-spacing:.14em;text-transform:uppercase;
  color:var(--muted)}}
.facts dd{{font-size:var(--step-0);font-weight:600;margin-top:.15rem}}
.stars{{color:var(--accent);letter-spacing:2px}}
section{{padding-block:clamp(3rem,7vw,5.5rem)}}
.sec-h{{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;
  gap:1rem;margin-bottom:2.2rem;padding-bottom:.9rem;border-bottom:1px solid var(--line)}}
h2{{font-size:var(--step-2)}}
.sub{{color:var(--muted);font-size:var(--step--1)}}
/* menu list with leader dots */
.menu{{list-style:none;display:grid;gap:1.6rem}}
@media(min-width:760px){{.menu{{grid-template-columns:1fr 1fr;column-gap:3.5rem}}}}
.item-h{{display:flex;align-items:baseline;gap:.6rem}}
.item h3{{font-size:var(--step-1)}}
.dots{{flex:1;border-bottom:1px dotted var(--line);transform:translateY(-.2em)}}
.item p{{color:var(--muted);font-size:var(--step--1);margin-top:.35rem;max-width:46ch}}
.panel{{background:var(--paper);border:1px solid var(--line);border-radius:var(--rc)}}
.split{{display:grid;gap:0}}
@media(min-width:820px){{.split{{grid-template-columns:1fr 1fr}}}}
.split > div{{padding:clamp(1.6rem,3vw,2.4rem)}}
.split > div + div{{border-top:1px solid var(--line)}}
@media(min-width:820px){{.split > div + div{{border-top:0;border-left:1px solid var(--line)}}}}
table{{width:100%;border-collapse:collapse;font-size:var(--step--1)}}
th,td{{text-align:left;padding:.55rem 0;border-bottom:1px solid var(--line)}}
th{{font-weight:600;color:var(--muted)}}
td{{text-align:right;font-variant-numeric:tabular-nums}}
tr:last-child th,tr:last-child td{{border-bottom:0}}
.map{{width:100%;height:300px;border:0;display:block;border-radius:var(--rc);margin-top:1.4rem}}
#claim{{background:var(--ink);color:var(--surface)}}
#claim h2{{color:var(--surface);max-width:20ch}}
#claim p{{opacity:.85;max-width:56ch;margin-top:1rem}}
#claim .price{{opacity:1;font-weight:600;margin-top:1.4rem}}
.note{{font-size:12.5px;color:var(--muted);padding-block:2.2rem;max-width:70ch}}
footer{{border-top:1px solid var(--line);padding-block:1.6rem;
  font-size:12.5px;color:var(--muted);display:flex;flex-wrap:wrap;
  justify-content:space-between;gap:.6rem}}
/* mobile: the one action that matters for a local business */
.callbar{{position:fixed;left:0;right:0;bottom:0;z-index:80;display:none;
  background:var(--accent);color:var(--ink);text-align:center;padding:15px;
  font-weight:700;text-decoration:none;
  box-shadow:0 -6px 20px color-mix(in srgb,var(--ink) 18%,transparent)}}
@media(max-width:700px){{.callbar{{display:block}} body{{padding-bottom:60px}}}}
@media print{{
  nav,.callbar,.wm,.claimbar,#claim,.map{{display:none!important}}
  body{{background:#fff;color:#000;font-size:11pt}}
  header{{padding-block:0 1rem}} section{{padding-block:1rem}}
  .menu{{grid-template-columns:1fr 1fr}}
}}
</style></head><body>
<a class="skip" href="#main">Skip to content</a>
{mark}
<nav aria-label="Primary"><div class="wrap">
  <span class="brand">{name_s}</span>
  <ul>
    <li><a href="#menu">{sec0}</a></li>
    <li><a href="#visit">Visit</a></li>
    <li>{f'<a class="btn" href="tel:{tel}">Call</a>' if tel else '<a class="btn" href="#claim">Get yours</a>'}</li>
  </ul>
</div></nav>

<header><div class="wrap grid">
  <div>
    <p class="eyebrow">{e(meta['label'])}{(' · ' + e(city.title())) if city else ''}</p>
    <h1>{name_s}</h1>
    <p class="lede">{e(hero)}</p>
    <div class="actions">
      {f'<a class="btn" href="tel:{tel}">Call {phone_s}</a>' if tel else ''}
      <a class="btn ghost" href="#menu">See the {sec0.lower()}</a>
    </div>
  </div>
  <dl class="facts">
    {f'<div><dt>Rating</dt><dd><span class="stars">{"★" * int(round(float(rating)))}</span> {float(rating):.1f} on Google</dd></div>' if rating else ''}
    {f'<div><dt>Find us</dt><dd>{addr_s}</dd></div>' if addr_s else ''}
    {f'<div><dt>Call</dt><dd>{phone_s}</dd></div>' if phone_s else ''}
  </dl>
</div></header>

<main id="main">
<section id="menu"><div class="wrap">
  <div class="sec-h"><h2>{sec0}</h2>
    <p class="sub">Sample layout — your real items and prices go here.</p></div>
  <ul class="menu">{menu_html}</ul>
</div></section>

<section id="visit"><div class="wrap">
  <div class="sec-h"><h2>Visit</h2><p class="sub">Replace with your real details.</p></div>
  <div class="panel split">
    <div>
      <h3 style="font-size:var(--step-1);margin-bottom:.9rem">Hours</h3>
      <table><tbody>
        <tr><th scope="row">Mon – Thu</th><td>11:00 – 21:00</td></tr>
        <tr><th scope="row">Fri – Sat</th><td>11:00 – 22:00</td></tr>
        <tr><th scope="row">Sunday</th><td>12:00 – 20:00</td></tr>
      </tbody></table>
      <p class="sub" style="margin-top:1rem">Placeholder hours — send us your real ones.</p>
    </div>
    <div>
      <h3 style="font-size:var(--step-1);margin-bottom:.9rem">Where</h3>
      <p>{addr_s or 'Your address here'}</p>
      {f'<p style="margin-top:.8rem"><a class="btn ghost" href="tel:{tel}">{phone_s}</a></p>' if tel else ''}
    </div>
  </div>
  {map_html}
</div></section>

<section id="claim"><div class="wrap">
  <h2>Want this as your real website?</h2>
  <p>This sample was built for {name_s} at no cost, and nothing is published.
     If you want it live on your own domain — with your real {sec0.lower()}, hours
     and photos — reply to the email that brought you here.</p>
  <p class="price">One-time setup: ${PRICE_USD}. No subscription.</p>
  <p>If you'd rather not hear from us again, every email has a one-click opt-out.</p>
</div></section>
</main>

<div class="wrap">
  <p class="note">Sample content is marked as such. Business name, address, phone and
  rating come from public Google Places data. Not affiliated with or endorsed by
  {name_s}.</p>
  <footer>
    <span>© {year} {name_s}</span>
    <span>Preview {datetime.now().strftime('%b %d, %Y')} · ref {token}</span>
  </footer>
</div>
{f'<a class="callbar" href="tel:{tel}">Call {phone_s}</a>' if tel else ''}
</body></html>""", token


if __name__ == "__main__":
    h, t = generate_site("Taqueria La Esquina", "1234 Navigation Blvd, Houston, TX",
                         "(713) 555-0142", "restaurant", 4.6, "houston", 1, 1)
    from pathlib import Path
    p = Path(__file__).parent / "demos" / f"sample-{t}.html"
    p.parent.mkdir(exist_ok=True)
    p.write_text(h)
    print(f"wrote {p}")
