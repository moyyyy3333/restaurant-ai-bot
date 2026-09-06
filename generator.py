"""
Demo site generator.

One self-contained HTML file per business — no build step, no external assets,
so it renders instantly from the server or from disk. Category-aware copy comes
from config.BUSINESS_CATEGORIES; visual systems come from config.CATEGORY_THEMES.

Everything the business didn't give us is clearly marked as sample content, so
the demo never puts false claims (fake prices, fake hours) in a real business's
name.
"""

import html
import json
import re
import secrets
from datetime import datetime

from config import (BUSINESS_CATEGORIES, CARE_MONTHLY_USD, CARE_YEARLY_USD,
                    PRICE_USD, theme_for)
from profiles import (FOOD_CATEGORIES, PROFILES, TRADE_CATEGORIES, infer_cuisine,
                      looks_generic, profile_for)
from writer import write_copy

# Mood is a light overlay on top of the category family — not a reskin.
MOOD_STYLES = {
    "classic": dict(h_weight="400", radius_card="12px", radius_cta="4px", tag_ls=".28em"),
    "minimal": dict(h_weight="300", radius_card="2px", radius_cta="2px", tag_ls=".36em"),
    "warm": dict(h_weight="500", radius_card="20px", radius_cta="999px", tag_ls=".18em"),
    "bold": dict(h_weight="700", radius_card="4px", radius_cta="2px", tag_ls=".06em"),
}

SAMPLE = {
    "restaurant": [
        ("Seasonal plates", "Changes with the market"),
        ("House specialty", "Ask about today's preparation"),
        ("Family platter", "Made for sharing"),
        ("Daily soup", "The kitchen's call"),
        ("Something sweet", "Ask what's on"),
    ],
    "cafe": [
        ("Espresso", "Single or double"),
        ("Pour over", "Rotating beans"),
        ("House drip", "All day"),
        ("Fresh pastry", "Baked each morning"),
        ("Seasonal drink", "Changes with the weather"),
    ],
    "bakery": [
        ("Morning breads", "Out of the oven by 7"),
        ("Pastry case", "Changes daily"),
        ("Custom cakes", "Order ahead"),
        ("Cookies & slices", "By the piece"),
        ("Sandwich loaves", "Ask what's left"),
    ],
    "barber": [
        ("Haircut", "Classic or modern"),
        ("Beard trim", "Hot towel finish"),
        ("Skin fade", "Ask for a consult"),
        ("Kids cut", "Ages 12 and under"),
        ("Hot shave", "When time allows"),
    ],
    "salon": [
        ("Cut & style", "Consultation included"),
        ("Color", "Full or partial"),
        ("Treatment", "Ask about options"),
        ("Blowout", "Walk-ins when we can"),
        ("Event style", "Book ahead"),
    ],
    "auto": [
        ("Diagnostics", "Know before you spend"),
        ("Brakes & tires", "Same-day on most cars"),
        ("Oil change", "While you wait"),
        ("Inspection", "Ask about readiness"),
        ("A/C & electrical", "We diagnose first"),
    ],
    "gym": [
        ("Open gym", "Free weights and machines"),
        ("Classes", "Check the board"),
        ("Personal training", "First session intro"),
        ("Cardio floor", "Open during hours"),
        ("Day pass", "Ask at the desk"),
    ],
    "florist": [
        ("Everyday bouquet", "Designer's choice"),
        ("Events", "Consultation available"),
        ("Same-day delivery", "Order by noon"),
        ("Plants", "In the shop"),
        ("Sympathy", "Call and we'll help"),
    ],
    "dentist": [
        ("Cleanings", "Every six months"),
        ("Whitening", "In-office or take-home"),
        ("Emergency care", "Same-day when we can"),
        ("Restorative", "By consultation"),
        ("New patients", "Ask about openings"),
    ],
    "lawyer": [
        ("Consultation", "Ask about your case"),
        ("Representation", "By practice area"),
        ("Documents", "Review and preparation"),
        ("Negotiation", "When talking is cheaper"),
        ("Referrals", "If we are not the right fit"),
    ],
    "plumber": [
        ("Repairs", "Leaks, clogs, and more"),
        ("Water heaters", "Install and repair"),
        ("Emergency service", "Available on call"),
        ("Drain clearing", "Same-day when we can"),
        ("Fixtures", "Swap and install"),
    ],
    "electrician": [
        ("Repairs", "Diagnose and fix"),
        ("Panel upgrades", "Bring it up to code"),
        ("New installs", "Fixtures and wiring"),
        ("Safety check", "Ask about a walkthrough"),
        ("Emergency call", "When the power is out"),
    ],
    "roofer": [
        ("Repairs", "Leaks and storm damage"),
        ("Replacement", "Full tear-off and install"),
        ("Inspection", "Estimate on request"),
        ("Gutters", "Clean and repair"),
        ("Emergency tarp", "After weather"),
    ],
    "locksmith": [
        ("Lockouts", "Home, auto, business"),
        ("Rekeying", "Same-day service"),
        ("New locks", "Installed on the spot"),
        ("Keys", "Cut while you wait"),
        ("Safes", "Ask about options"),
    ],
    "jewelry": [
        ("Custom pieces", "Designed with you"),
        ("Repairs", "Sizing and fixes"),
        ("Appraisals", "By appointment"),
        ("Resetting", "Old stones, new setting"),
        ("Watches", "Ask what we service"),
    ],
    "tattoo": [
        ("Custom work", "Your design or ours"),
        ("Flash", "Walk-ins welcome"),
        ("Touch-ups", "Ask about our policy"),
        ("Cover-ups", "Consultation first"),
        ("Consult", "Bring references"),
    ],
    "veterinary": [
        ("Wellness exams", "Yearly checkups"),
        ("Vaccinations", "Keep them protected"),
        ("Urgent care", "Call ahead"),
        ("Dental", "By recommendation"),
        ("New patients", "Ask about openings"),
    ],
    "optician": [
        ("Eye exams", "By appointment"),
        ("Frames", "Wide selection in stock"),
        ("Contacts", "Fitting included"),
        ("Adjustments", "Walk-in welcome"),
        ("Lenses", "Ask about options"),
    ],
    "dry_cleaning": [
        ("Dry cleaning", "Ready in two days"),
        ("Alterations", "While you wait when we can"),
        ("Wash & fold", "Drop off anytime"),
        ("Pressing", "Shirts and trousers"),
        ("Household", "Ask about bedding"),
    ],
    "photo": [
        ("Portraits", "Studio or on location"),
        ("Events", "Full coverage"),
        ("Prints", "Same-week turnaround"),
        ("Families", "Ask about sessions"),
        ("Headshots", "In-studio"),
    ],
    "accountant": [
        ("Bookkeeping", "Monthly or quarterly"),
        ("Tax prep", "Individual and business"),
        ("Consulting", "By appointment"),
        ("Payroll", "Ask about setup"),
        ("Year-end", "Plan ahead"),
    ],
    "estate_agent": [
        ("Buying", "Guided every step"),
        ("Selling", "Priced to move"),
        ("Rentals", "Ask about availability"),
        ("Valuation", "No obligation"),
        ("Neighborhoods", "We work where we live"),
    ],
    "insurance": [
        ("Auto", "Quote on request"),
        ("Home", "Bundle when it helps"),
        ("Life", "Talk to an agent"),
        ("Business", "Ask about coverage"),
        ("Claims help", "We walk you through it"),
    ],
    "pet": [
        ("Food & supplies", "In stock"),
        ("Grooming", "By appointment"),
        ("Advice", "Ask our staff"),
        ("Treats", "Behind the counter"),
        ("Special orders", "Give us a day"),
    ],
    "hardware": [
        ("Tools", "For every job"),
        ("Paint", "Custom mixed"),
        ("Key cutting", "While you wait"),
        ("Fasteners", "Bins by the aisle"),
        ("Advice", "Ask who is on the floor"),
    ],
    "books": [
        ("New releases", "Restocked weekly"),
        ("Used & rare", "Always changing"),
        ("Events", "Readings and signings"),
        ("Staff picks", "On the front table"),
        ("Orders", "If we do not have it"),
    ],
}


def _monogram(name: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name or "")
             if w.lower() not in {"the", "a", "an", "and", "of", "la", "el", "los", "las"}]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    if words:
        return words[0][:2].upper()
    return (name or "·")[:1].upper()


def _esc(value) -> str:
    return html.escape(str(value or ""))


# OSM/Nominatim display_name trails with county + state name + zip + country.
# Humans want street + city + state/zip. Maps still get the original string.
_COUNTRY_PART = re.compile(
    r"^(united states( of america)?|u\.s\.a\.?|usa|u\.s\.|us|canada|mexico)$",
    re.I,
)
_COUNTY_PART = re.compile(
    r"\b(county|parish|borough|census area|municipality)\b",
    re.I,
)
_ZIP_PART = re.compile(r"^\d{5}(?:-\d{4})?$")
_HOUSE_NO = re.compile(r"^\d+[A-Za-z]?$")
_STREETISH = re.compile(
    r"\d.+\s+\w+|\b(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|"
    r"ln|lane|way|pkwy|parkway|hwy|highway|ct|court|pl|place|ter|terrace)\b",
    re.I,
)
_US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
_STATE_ABBR = set(_US_STATES.values())
_STATE_ZIP = re.compile(
    r"^([A-Za-z. ]+?)\s+(\d{5}(?:-\d{4})?)$"
)


def _norm_addr_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _state_abbr(part: str) -> str:
    token = (part or "").strip()
    if len(token) == 2 and token.upper() in _STATE_ABBR:
        return token.upper()
    return _US_STATES.get(token.lower(), "")


def _state_and_zip(part: str):
    m = _STATE_ZIP.match((part or "").strip())
    if not m:
        return "", ""
    abbr = _state_abbr(m.group(1))
    if not abbr:
        return "", ""
    return abbr, m.group(2)


def _looks_like_street(text: str) -> bool:
    return bool(_STREETISH.search(text or ""))


def human_address(address: str, name: str = "", city: str = "") -> str:
    """Shorten OSM/Places display strings for people.

    '2100, Yale Street, Houston Heights, Houston, Harris County, Texas,
    77008, United States' → '2100 Yale Street, Houston, TX 77008'.
    Already-short strings ('1234 Navigation Blvd, Houston, TX') stay put.
    """
    raw = (address or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return raw
    if name and _norm_addr_token(parts[0]) == _norm_addr_token(name):
        parts = parts[1:]
    if len(parts) >= 2 and _HOUSE_NO.match(parts[0]) and not _HOUSE_NO.match(parts[1]):
        parts = [f"{parts[0]} {parts[1]}"] + parts[2:]

    used = set()
    state = ""
    zipcode = ""
    for i in range(len(parts) - 1, -1, -1):
        part = parts[i]
        if _COUNTRY_PART.match(part) or _COUNTY_PART.search(part):
            used.add(i)
            continue
        pair_state, pair_zip = _state_and_zip(part)
        if pair_state and not state:
            state, zipcode = pair_state, pair_zip or zipcode
            used.add(i)
            continue
        if _ZIP_PART.match(part) and not zipcode:
            zipcode = part
            used.add(i)
            continue
        abbr = _state_abbr(part)
        if abbr and not state:
            state = abbr
            used.add(i)
            continue

    remaining = [p for i, p in enumerate(parts) if i not in used]
    if not remaining and not (state or zipcode):
        return raw

    street = remaining[0] if remaining else ""
    city_part = ""
    want_city = (city or "").strip()
    if want_city:
        want = _norm_addr_token(want_city)
        fuzzy = ""
        for part in remaining[1:]:
            token = _norm_addr_token(part)
            if token == want:
                city_part = part
                break
            if not fuzzy and want and (want in token or token in want):
                fuzzy = part
        if not city_part:
            city_part = fuzzy
    if not city_part and len(remaining) >= 2:
        city_part = remaining[-1]
        if city_part.lower() == street.lower():
            city_part = ""

    bits = [b for b in (street, city_part) if b]
    tail = " ".join(x for x in (state, zipcode) if x)
    if tail:
        bits.append(tail)
    parsed = ", ".join(bits)
    if not parsed or not re.search(r"[A-Za-z]", parsed):
        return raw
    if _looks_like_street(raw) and street and not _looks_like_street(street):
        return raw
    return parsed


def _hours_rows(hours) -> str:
    rows = []
    for day, time in hours:
        rows.append(f"<tr><th scope=\"row\">{_esc(day)}</th><td>{_esc(time)}</td></tr>")
    return "".join(rows)


def _price_span(price) -> str:
    if not price:
        return '<span class="price-n">Ask</span>'
    return f'<span class="price-n">${int(price)}</span>'


def _triples(items):
    out = []
    for row in items:
        if len(row) >= 3:
            out.append((row[0], row[1], row[2]))
        else:
            out.append((row[0], row[1], None))
    return out


def _offer_html(family: str, items) -> str:
    rows = _triples(items)
    if family == "bakery":
        return "".join(
            f'<article class="case-card"><div class="item-h"><h3>{_esc(t)}</h3>'
            f'{_price_span(p)}</div><p>{_esc(d)}</p></article>'
            for t, d, p in rows)
    if family in {"chair", "trade", "floor"}:
        out = []
        for i, (t, d, p) in enumerate(rows, 1):
            out.append(
                f'<li class="num-item"><span class="n" aria-hidden="true">{i:02d}</span>'
                f'<div><div class="item-h"><h3>{_esc(t)}</h3>{_price_span(p)}</div>'
                f'<p>{_esc(d)}</p></div></li>')
        return "".join(out)
    if family == "cafe":
        return "".join(
            f'<li class="board-row"><h3>{_esc(t)}</h3><span class="rule" aria-hidden="true"></span>'
            f'{_price_span(p)}<p>{_esc(d)}</p></li>'
            for t, d, p in rows)
    if family in {"practice", "clinic", "gallery", "library"}:
        return "".join(
            f'<li class="rule-item"><div class="item-h"><h3>{_esc(t)}</h3>{_price_span(p)}</div>'
            f'<p>{_esc(d)}</p></li>'
            for t, d, p in rows)
    return "".join(
        f'''<li class="item">
      <div class="item-h"><h3>{_esc(t)}</h3><span class="dots" aria-hidden="true"></span>{_price_span(p)}</div>
      <p>{_esc(d)}</p>
    </li>''' for t, d, p in rows)


def _lookup_place(name: str, address: str) -> dict:
    """Real hours/types from Google Places. Empty if unknown — never invent."""
    if not name:
        return {}
    try:
        from scanner.scanner import google_enrich
        return google_enrich(name, address or "", timeout=4, check_liveness=False) or {}
    except Exception:
        return {}


def _offer_wrap(family: str, inner: str) -> str:
    if family == "bakery":
        return f'<div class="case">{inner}</div>'
    if family in {"chair", "trade", "floor"}:
        return f'<ol class="nums">{inner}</ol>'
    if family == "cafe":
        return f'<ul class="board">{inner}</ul>'
    if family in {"practice", "clinic", "gallery", "library"}:
        return f'<ul class="rules">{inner}</ul>'
    return f'<ul class="menu">{inner}</ul>'


def _css(theme: dict, mood: dict) -> str:
    dark = theme["ink"]
    accent = theme["accent"]
    light = theme["surface"]
    paper = theme["paper"]
    hero_bg = theme["hero_bg"]
    hero_fg = theme["hero_fg"]
    muted = theme["muted"]
    display = theme["display"]
    body = theme["body"]
    return f"""
:root{{
  --ink:{dark}; --accent:{accent}; --surface:{light}; --paper:{paper};
  --hero:{hero_bg}; --on-hero:{hero_fg};
  --muted:{muted};
  --line:color-mix(in srgb, {dark} 12%, {light});
  --line-strong:color-mix(in srgb, {dark} 22%, {light});
  --step--1:clamp(.78rem,.74rem + .16vw,.88rem);
  --step-0:clamp(1rem,.95rem + .22vw,1.125rem);
  --step-1:clamp(1.2rem,1.08rem + .55vw,1.55rem);
  --step-2:clamp(1.7rem,1.35rem + 1.4vw,2.55rem);
  --step-3:clamp(2.6rem,1.7rem + 4.2vw,5.2rem);
  --gap:clamp(1.6rem,1.1rem + 2.2vw,3.4rem);
  --rc:{mood['radius_card']}; --rb:{mood['radius_cta']};
  --display:{display}; --body:{body};
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
@media (prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}
  *{{animation:none!important;transition:none!important}}}}
body{{font-family:var(--body);background:var(--surface);color:var(--ink);
  font-size:var(--step-0);line-height:1.62;-webkit-font-smoothing:antialiased}}
h1,h2,h3,.brand,.mono{{font-family:var(--display);font-weight:{mood['h_weight']};
  line-height:1.05;letter-spacing:-.02em;text-wrap:balance}}
a{{color:inherit}}
:focus-visible{{outline:3px solid var(--accent);outline-offset:3px;border-radius:2px}}
.skip{{position:absolute;left:-9999px}}
.skip:focus{{left:12px;top:12px;z-index:200;background:var(--ink);color:var(--surface);
  padding:10px 16px;border-radius:var(--rb)}}
.wrap{{width:min(1120px,calc(100% - clamp(32px,6vw,64px)));margin-inline:auto}}
.wm{{position:fixed;top:14px;right:14px;background:var(--ink);color:var(--accent);
  padding:6px 14px;border-radius:99px;font-size:11px;letter-spacing:.22em;z-index:99}}
.claimbar{{background:var(--ink);color:var(--surface);text-align:center;
  padding:11px 18px;font-size:var(--step--1)}}
.claimbar a{{color:var(--accent)}}
nav{{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--surface) 82%,transparent);
  backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}}
nav .wrap{{display:flex;align-items:center;justify-content:space-between;
  gap:1rem;padding-block:16px}}
nav .brand{{font-weight:600;font-size:var(--step-0);letter-spacing:-.01em}}
nav ul{{display:flex;align-items:center;gap:clamp(16px,2.6vw,32px);list-style:none}}
nav a{{text-decoration:none;font-size:var(--step--1);color:var(--muted)}}
nav a:hover{{color:var(--ink)}}
.btn{{display:inline-flex;align-items:center;justify-content:center;min-height:48px;
  background:var(--accent);color:var(--ink);font-weight:650;padding:0 1.25em;
  border-radius:var(--rb);text-decoration:none;border:1px solid transparent;
  transition:filter .15s ease}}
.btn:hover{{filter:brightness(1.06)}}
.btn.ghost{{background:transparent;border-color:var(--line-strong);color:var(--ink)}}
.btn.on-dark{{background:var(--accent);color:var(--ink)}}
.btn.on-dark.ghost{{background:color-mix(in srgb,var(--on-hero) 8%,transparent);
  border-color:color-mix(in srgb,var(--on-hero) 48%,transparent);color:var(--on-hero)}}

/* —— heroes —— */
.hero{{position:relative;overflow:hidden}}
.hero .eyebrow{{font-size:var(--step--1);letter-spacing:{mood['tag_ls']};
  text-transform:uppercase;color:var(--accent);font-weight:650;margin-bottom:1.1rem}}
.hero h1{{font-size:var(--step-3);margin-bottom:.8rem}}
.hero .lede{{font-size:var(--step-1);line-height:1.3;max-width:28ch}}
.hero .atmosphere{{margin-top:1rem;color:var(--muted);max-width:42ch;font-size:var(--step--1)}}
.hero .actions{{display:flex;flex-wrap:wrap;gap:12px;margin-top:2rem}}
.hero .hairline{{width:min(72px,20vw);height:1px;background:var(--accent);border:0;margin:1.2rem 0}}
.facts{{display:grid;gap:1.15rem}}
.facts dt{{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}}
.facts dd{{font-weight:600;margin-top:.2rem}}
.stars{{color:var(--accent);letter-spacing:2px}}
.mono{{width:88px;height:88px;border:1px solid var(--accent);border-radius:50%;
  display:grid;place-items:center;font-size:1.6rem;letter-spacing:.08em;color:var(--accent)}}

.family-supper .hero,.family-luxe .hero,.family-gallery .hero,.family-floor .hero,
.family-practice .hero,.family-chair .hero,.family-library .hero,.family-trade .hero{{
  background:var(--hero);color:var(--on-hero);padding-block:clamp(4.2rem,11vw,8.2rem) clamp(3rem,7vw,5.5rem)}}
.family-supper .hero .lede,.family-luxe .hero .lede,.family-gallery .hero .lede,
.family-floor .hero .lede,.family-practice .hero .lede,.family-chair .hero .lede,
.family-library .hero .lede,.family-trade .hero .lede{{color:color-mix(in srgb,var(--on-hero) 78%,transparent)}}
.family-supper .hero .atmosphere,.family-luxe .hero .atmosphere,.family-gallery .hero .atmosphere,
.family-floor .hero .atmosphere,.family-practice .hero .atmosphere,.family-chair .hero .atmosphere,
.family-library .hero .atmosphere,.family-trade .hero .atmosphere{{
  color:color-mix(in srgb,var(--on-hero) 62%,transparent)}}
.family-supper .facts dt,.family-luxe .facts dt,.family-gallery .facts dt,
.family-floor .facts dt,.family-practice .facts dt,.family-chair .facts dt,
.family-library .facts dt,.family-trade .facts dt{{
  color:color-mix(in srgb,var(--on-hero) 55%,transparent)}}
.family-supper nav,.family-luxe nav,.family-gallery nav,.family-floor nav,
.family-practice nav,.family-chair nav,.family-library nav,.family-trade nav{{
  background:color-mix(in srgb,var(--hero) 88%,transparent);border-bottom-color:color-mix(in srgb,var(--on-hero) 12%,transparent)}}
.family-supper nav .brand,.family-luxe nav .brand,.family-gallery nav .brand,
.family-floor nav .brand,.family-practice nav .brand,.family-chair nav .brand,
.family-library nav .brand,.family-trade nav .brand{{color:var(--on-hero)}}
.family-supper nav a,.family-luxe nav a,.family-gallery nav a,.family-floor nav a,
.family-practice nav a,.family-chair nav a,.family-library nav a,.family-trade nav a{{
  color:color-mix(in srgb,var(--on-hero) 70%,transparent)}}
.family-supper nav a:hover,.family-luxe nav a:hover,.family-gallery nav a:hover,
.family-floor nav a:hover,.family-practice nav a:hover,.family-chair nav a:hover,
.family-library nav a:hover,.family-trade nav a:hover{{color:var(--on-hero)}}

.hero-grid{{display:grid;grid-template-columns:1fr;gap:var(--gap);align-items:end}}
@media(min-width:860px){{.hero-grid{{grid-template-columns:1.4fr .7fr}}}}
.family-supper .hero,.family-luxe .hero{{
  background:
    radial-gradient(900px 420px at 110% -10%, color-mix(in srgb,var(--accent) 18%,transparent), transparent 55%),
    var(--hero)}}
.family-gallery .hero{{padding-block:clamp(5rem,14vw,10rem) clamp(3.5rem,8vw,6rem)}}
.family-floor .hero h1{{letter-spacing:-.04em;text-transform:uppercase}}
.family-chair .hero{{
  background:
    repeating-linear-gradient(90deg, transparent, transparent 46px, color-mix(in srgb,var(--on-hero) 6%,transparent) 46px, color-mix(in srgb,var(--on-hero) 6%,transparent) 47px),
    var(--hero)}}
.family-chair .hero-grid{{justify-items:center;text-align:center}}
.family-chair .hero .lede,.family-chair .hero .atmosphere{{margin-inline:auto}}
.family-chair .hairline{{margin-inline:auto}}
.family-chair .facts{{justify-items:center}}
.family-practice .hero-grid{{justify-items:center;text-align:center;max-width:46rem;margin-inline:auto}}
.family-practice .hero .lede,.family-practice .hero .atmosphere{{margin-inline:auto}}
.family-practice .hairline{{margin-inline:auto;width:min(120px,30vw)}}
.family-practice .facts{{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));width:100%;text-align:left}}
.family-trade .hero .lede{{max-width:22ch;font-family:var(--display);font-size:var(--step-2)}}
.family-library .hero{{
  background:
    linear-gradient(180deg, transparent, color-mix(in srgb,var(--accent) 10%,transparent)),
    var(--hero)}}

.family-cafe .hero,.family-bakery .hero,.family-atelier .hero,.family-clinic .hero,
.family-counter .hero{{
  background:var(--hero);color:var(--on-hero);padding-block:clamp(3.6rem,9vw,7rem) clamp(2.6rem,6vw,4.6rem)}}
.family-cafe .ticket{{background:var(--paper);border:1px solid var(--line);border-radius:var(--rc);
  padding:1.4rem 1.5rem;box-shadow:0 18px 40px color-mix(in srgb,var(--ink) 6%,transparent)}}
.family-bakery .hero h1{{font-style:italic}}
.family-atelier .hero .lede{{font-style:italic;max-width:24ch}}
.family-clinic .hero{{background:
  radial-gradient(800px 360px at 0% 0%, color-mix(in srgb,var(--accent) 14%,transparent), transparent 60%),
  var(--hero)}}

/* —— sections —— */
section{{padding-block:clamp(3.2rem,7.5vw,6rem)}}
.sec-h{{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;
  gap:1rem;margin-bottom:2.4rem;padding-bottom:1rem;border-bottom:1px solid var(--line)}}
h2{{font-size:var(--step-2)}}
.kicker{{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);
  font-weight:650;margin-bottom:.45rem}}
.sub{{color:var(--muted);font-size:12.5px;letter-spacing:.01em;max-width:36ch}}
.menu{{list-style:none;display:grid;gap:1.7rem}}
@media(min-width:760px){{.menu{{grid-template-columns:1fr 1fr;column-gap:4rem}}}}
.item-h{{display:flex;align-items:baseline;gap:.65rem}}
.item h3{{font-size:var(--step-1)}}
.dots{{flex:1;border-bottom:1px dotted var(--line-strong);transform:translateY(-.22em)}}
.item p{{color:var(--muted);font-size:var(--step--1);margin-top:.4rem;max-width:46ch}}
.price-n{{font-variant-numeric:tabular-nums;font-weight:650;font-size:var(--step--1);
  color:var(--ink);white-space:nowrap}}
.hero-visual{{margin:0;position:relative;border-radius:var(--rc);overflow:hidden;
  min-height:min(52vw,320px);color:var(--ink);border:1px solid var(--line)}}
.hero-visual .photo{{position:absolute;inset:0;background:
    radial-gradient(90% 70% at 80% 10%, color-mix(in srgb,var(--accent) 42%,transparent), transparent 58%),
    linear-gradient(165deg, color-mix(in srgb,var(--ink) 18%,var(--paper)), var(--paper))}}
.hero-visual[data-visual="pho"] .photo{{background:
    radial-gradient(70% 60% at 30% 80%, #8a3a18 0%, transparent 55%),
    linear-gradient(160deg, #2a1610, #7a4a28)}}
.hero-visual[data-visual="crepe"] .photo{{background:
    radial-gradient(80% 50% at 70% 20%, #f0c98a, transparent 50%),
    linear-gradient(160deg, #5a3a22, #c4a06a)}}
.hero-visual[data-visual="pizza"] .photo{{background:
    radial-gradient(70% 60% at 50% 50%, #d45a2a, #5a2010)}}
.hero-visual[data-visual="ice_cream"] .photo{{background:
    radial-gradient(80% 70% at 30% 20%, #f7c8d8, transparent 50%),
    linear-gradient(165deg, #f4e6d8, #e8b8c8)}}
.hero-visual[data-visual="coffee"] .photo{{background:
    radial-gradient(70% 60% at 80% 0%, #d4a078, transparent 50%),
    linear-gradient(160deg, #3a2418, #8a5a38)}}
.hero-visual svg{{position:relative;width:100%;height:min(52vw,320px);display:block}}
.hero-visual figcaption{{position:absolute;left:14px;bottom:12px;font-size:10px;
  letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}}
.family-supper .hero-visual,.family-luxe .hero-visual,.family-gallery .hero-visual,
.family-floor .hero-visual,.family-practice .hero-visual,.family-chair .hero-visual,
.family-library .hero-visual,.family-trade .hero-visual{{
  background:
    radial-gradient(120% 80% at 80% 0%, color-mix(in srgb,var(--accent) 22%,transparent), transparent 55%),
    color-mix(in srgb,var(--on-hero) 6%,var(--hero));
  color:var(--on-hero);border-color:color-mix(in srgb,var(--on-hero) 16%,transparent)}}
.family-supper .hero-visual figcaption,.family-luxe .hero-visual figcaption,
.family-gallery .hero-visual figcaption,.family-floor .hero-visual figcaption,
.family-practice .hero-visual figcaption,.family-chair .hero-visual figcaption,
.family-library .hero-visual figcaption,.family-trade .hero-visual figcaption{{
  color:color-mix(in srgb,var(--on-hero) 62%,transparent)}}
.hero-aside{{display:grid;gap:1.2rem}}
.case{{display:grid;gap:1rem}}
@media(min-width:700px){{.case{{grid-template-columns:repeat(3,1fr)}}}}
.case-card{{background:var(--paper);border:1px solid var(--line);border-radius:var(--rc);
  padding:1.4rem 1.3rem 1.5rem}}
.case-card h3{{font-size:var(--step-1);font-style:italic;margin-bottom:.45rem}}
.case-card p{{color:var(--muted);font-size:var(--step--1)}}
.board{{list-style:none;background:var(--ink);color:var(--paper);border-radius:var(--rc);
  padding:clamp(1.4rem,3vw,2.2rem);display:grid;gap:1.1rem}}
.board-row{{display:grid;grid-template-columns:minmax(8rem,auto) 1fr auto;gap:.35rem .8rem;align-items:baseline}}
.board-row h3{{font-family:var(--display);font-size:var(--step-1);font-weight:500}}
.board-row .rule{{border-bottom:1px dotted color-mix(in srgb,var(--paper) 28%,transparent);
  transform:translateY(-.25em)}}
.board-row .price-n{{color:var(--paper)}}
.board-row p{{grid-column:1/-1;color:color-mix(in srgb,var(--paper) 68%,transparent);
  font-size:var(--step--1);text-align:left}}
.nums{{list-style:none;display:grid;gap:0;border-top:1px solid var(--line)}}
.num-item{{display:grid;grid-template-columns:4.2rem 1fr;gap:1rem;align-items:baseline;
  padding:1.25rem 0;border-bottom:1px solid var(--line)}}
.num-item .n{{font-family:var(--display);font-size:var(--step-1);color:var(--accent);letter-spacing:.06em}}
.num-item h3{{font-size:var(--step-1)}}
.num-item p{{color:var(--muted);font-size:var(--step--1);margin-top:.3rem}}
.rules{{list-style:none;display:grid;gap:0}}
@media(min-width:760px){{.family-practice .rules{{grid-template-columns:1fr 1fr;column-gap:3.5rem}}}}
.rule-item{{padding:1.2rem 0;border-bottom:1px solid var(--line)}}
.rule-item h3{{font-size:var(--step-1);margin-bottom:.35rem}}
.rule-item p{{color:var(--muted);font-size:var(--step--1)}}
.family-gallery .rules{{max-width:36rem}}
.panel{{background:var(--paper);border:1px solid var(--line);border-radius:var(--rc)}}
.split{{display:grid;gap:0}}
@media(min-width:820px){{.split{{grid-template-columns:1.1fr .9fr}}}}
.split > div{{padding:clamp(1.6rem,3vw,2.5rem)}}
.split > div + div{{border-top:1px solid var(--line)}}
@media(min-width:820px){{.split > div + div{{border-top:0;border-left:1px solid var(--line)}}}}
table{{width:100%;border-collapse:collapse;font-size:var(--step--1)}}
th,td{{text-align:left;padding:.6rem 0;border-bottom:1px solid var(--line)}}
th{{font-weight:600;color:var(--muted)}}
td{{text-align:right;font-variant-numeric:tabular-nums}}
tr:last-child th,tr:last-child td{{border-bottom:0}}
.map{{width:100%;height:300px;border:0;display:block;border-radius:var(--rc);margin-top:1.5rem}}
#claim{{background:var(--ink);color:var(--surface)}}
#claim .kicker{{color:var(--accent)}}
#claim h2{{color:var(--surface);max-width:16ch;font-size:var(--step-2)}}
#claim p{{opacity:.86;max-width:52ch;margin-top:1rem}}
#claim .price{{opacity:1;font-weight:650;margin-top:1.5rem;font-size:var(--step-1)}}
#claim .hairline{{background:var(--accent)}}
.note{{font-size:12.5px;color:var(--muted);padding-block:2.2rem 0;max-width:70ch}}
footer{{border-top:1px solid var(--line);padding-block:1.7rem;margin-top:1.2rem;
  font-size:12.5px;color:var(--muted);display:flex;flex-wrap:wrap;
  justify-content:space-between;gap:.6rem}}
.callbar{{position:fixed;left:0;right:0;bottom:0;z-index:80;display:none;
  background:var(--accent);color:var(--ink);text-align:center;
  min-height:56px;padding:16px 16px calc(16px + env(safe-area-inset-bottom));
  font-weight:700;text-decoration:none;
  box-shadow:0 -8px 24px color-mix(in srgb,var(--ink) 16%,transparent)}}
@media(max-width:700px){{
  .callbar{{display:block}}
  body{{padding-bottom:calc(64px + env(safe-area-inset-bottom))}}
  nav .desk{{display:none}}
  .hero h1{{font-size:clamp(2.3rem,12vw,3.4rem)}}
  .board-row{{grid-template-columns:1fr;gap:.2rem}}
  .board-row p{{text-align:left}}
  .board-row .rule{{display:none}}
}}
@media print{{
  nav,.callbar,.wm,.claimbar,#claim,.map{{display:none!important}}
  body{{background:#fff;color:#000;font-size:11pt}}
  .hero{{padding-block:0 1rem;background:#fff;color:#000}}
  section{{padding-block:1rem}}
  .menu{{grid-template-columns:1fr 1fr}}
}}
"""


def generate_site(name, address="", phone="", category="restaurant", rating=None,
                  city="", lead_id=None, business_id=None, watermark=True, use_ai=True,
                  hours=None, place_types=None, fetch_place=False):
    """Returns (html_string, token).

    hours: list of (day, time) from Google Places, or None to look up when
    fetch_place=True. Unknown hours are omitted — never filled from a theme.
    """
    token = secrets.token_urlsafe(9)
    cat = category if category in BUSINESS_CATEGORIES else "restaurant"
    meta = BUSINESS_CATEGORIES[cat]
    theme = dict(theme_for(cat))

    shown_address = human_address(address, name=name, city=city)
    name_s, addr_s, phone_s = _esc(name), _esc(shown_address), _esc(phone)
    tel = "".join(ch for ch in str(phone or "") if ch.isdigit())
    city_s = _esc(city.title()) if city else ""

    extras = {}
    if fetch_place and (hours is None or place_types is None):
        extras = _lookup_place(name, address)
        if hours is None:
            hours = extras.get("hours")
        if place_types is None:
            place_types = extras.get("types")
    extra_text = " ".join(place_types or [])
    profile = profile_for(name, cat, extra_text)
    cuisine = infer_cuisine(name, cat, extra_text)
    if profile.get("theme_cat") in BUSINESS_CATEGORIES:
        theme = dict(theme_for(profile["theme_cat"]))
    ai = write_copy(name, meta["label"], city) if use_ai else None
    # Named cuisine profiles win over AI so "Thien An Sandwiches" cannot
    # become Grill/Catch/Pasta because a model ignored the name.
    if profile.get("items") and profile.get("cuisine") in PROFILES:
        hero = profile["tagline"] or meta["hero"]
        items = profile["items"]
    elif ai and ai["tagline"] and ai["items"] and not looks_generic(ai["items"]):
        hero = ai["tagline"]
        items = ai["items"]
    elif profile.get("items"):
        hero = profile["tagline"] or meta["hero"]
        items = profile["items"]
    else:
        hero = meta["hero"]
        items = SAMPLE.get(cat, SAMPLE["restaurant"])
    if ai and ai["accent"]:
        theme["accent"] = ai["accent"]
    mood_name = ai["mood"] if ai and ai["mood"] else "classic"
    mood = MOOD_STYLES.get(mood_name, MOOD_STYLES["classic"])
    family = profile.get("family") or theme["family"]
    label = profile.get("label") or meta["label"]
    atmosphere = profile.get("atmosphere") or theme["atmosphere"]
    offer_kicker = profile.get("offer_kicker") or theme["offer_kicker"]

    mark = ""

    map_html = ""
    if address:
        map_q = html.escape(str(address), quote=True)
        map_html = (f'<iframe class="map" loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
                    f'src="https://maps.google.com/maps?q={map_q}&output=embed"></iframe>')

    desc = _esc(hero)[:150]
    sec0 = _esc(meta["sections"][0])
    year = datetime.now().year
    menu_html = _offer_wrap(family, _offer_html(family, items))

    ld = {
        "@context": "https://schema.org", "@type": "LocalBusiness",
        "name": str(name), "description": str(hero),
    }
    if shown_address:
        ld["address"] = shown_address
    if phone:
        ld["telephone"] = str(phone)
    if rating:
        ld["aggregateRating"] = {"@type": "AggregateRating",
                                 "ratingValue": float(rating), "bestRating": 5}
    ld_json = json.dumps(ld)

    facts = []
    if rating:
        stars = "★" * int(round(float(rating)))
        facts.append(
            f'<div><dt>Rating</dt><dd><span class="stars">{stars}</span> '
            f'{float(rating):.1f} on Google</dd></div>')
    if addr_s:
        facts.append(f'<div><dt>Find us</dt><dd>{addr_s}</dd></div>')
    if phone_s:
        facts.append(f'<div><dt>Call</dt><dd>{phone_s}</dd></div>')
    facts_html = f'<dl class="facts">{"".join(facts)}</dl>' if facts else ""

    place = f"{_esc(label)}{(' · ' + city_s) if city_s else ''}"
    if cat in FOOD_CATEGORIES:
        cta_a, cta_b, href_b = "Call", "Order", "#menu"
        # Counters (ice cream, bánh mì, sandwiches) take orders — no table to reserve.
        if profile.get("reserve", True):
            cta_c, href_c = "Reserve", "#visit"
        else:
            cta_c, href_c = "", ""
    elif cat in TRADE_CATEGORIES:
        cta_a, cta_b, cta_c = ("Call", "Book", "Get a quote")
        href_b, href_c = "#visit", "#claim"
    else:
        cta_a, cta_b, cta_c = (theme["cta"], theme["cta_ghost"], "Visit")
        href_b, href_c = "#menu", "#visit"
    primary = (f'<a class="btn on-dark" href="tel:{tel}">{_esc(cta_a)}</a>'
               if tel else f'<a class="btn on-dark" href="#claim">{_esc(cta_a)}</a>')
    ghost = f'<a class="btn on-dark ghost" href="{href_b}">{_esc(cta_b)}</a>'
    if cta_c:
        ghost += f'<a class="btn on-dark ghost" href="{href_c}">{_esc(cta_c)}</a>'
    nav_call = (f'<a class="btn" href="tel:{tel}">Call</a>' if tel
                else '<a class="btn" href="#claim">Get yours</a>')
    # Honest omission: no fake photo frames or "sample image" chrome.
    aside = (
        f'<aside class="hero-aside">'
        f'<div class="mono" aria-hidden="true">{_esc(_monogram(name))}</div>'
        f'{facts_html}</aside>'
    )
    if family in {"cafe", "bakery", "atelier", "clinic", "counter"}:
        aside = f'<div class="ticket">{facts_html}</div>' if facts_html else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="{theme['hero_bg']}">
<meta name="description" content="{desc}">
<meta property="og:title" content="{name_s}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<title>{name_s}{(' · ' + city_s) if city_s else ''}</title>
<script type="application/ld+json">{ld_json}</script>
<style>{_css(theme, mood)}</style></head>
<body class="family-{family} mood-{mood_name}" data-family="{family}" data-category="{cat}" data-cuisine="{cuisine}">
<a class="skip" href="#main">Skip to content</a>
{mark}
<nav aria-label="Primary"><div class="wrap">
  <span class="brand">{name_s}</span>
  <ul>
    <li class="desk"><a href="#menu">{sec0}</a></li>
    <li class="desk"><a href="#visit">Visit</a></li>
    <li>{nav_call}</li>
  </ul>
</div></nav>

<header class="hero"><div class="wrap hero-grid">
  <div>
    <p class="eyebrow">{place}</p>
    <h1>{name_s}</h1>
    <hr class="hairline">
    <p class="lede">{_esc(hero)}</p>
    <p class="atmosphere">{_esc(atmosphere)}</p>
    <div class="actions">{primary}{ghost}</div>
  </div>
  {aside}
</div></header>

<main id="main">
<section id="menu"><div class="wrap">
  <div class="sec-h">
    <div><p class="kicker">{_esc(offer_kicker)}</p><h2>{sec0}</h2></div>
  </div>
  {menu_html}
  <p class="sub" style="margin-top:1.2rem">Sample prices — your real {sec0.lower()} replaces these.</p>
</div></section>

<section id="visit"><div class="wrap">
  <div class="sec-h">
    <div><p class="kicker">{_esc(theme['visit_kicker'])}</p><h2>Visit</h2></div>
  </div>
  <div class="panel split">
    {f'''<div>
      <h3 style="font-size:var(--step-1);margin-bottom:.9rem">Hours</h3>
      <table><tbody>{_hours_rows(hours)}</tbody></table>
    </div>''' if hours else ''}
    <div>
      <h3 style="font-size:var(--step-1);margin-bottom:.9rem">Where</h3>
      <p>{addr_s or 'Your address here'}</p>
      {f'<p style="margin-top:1rem"><a class="btn ghost" href="tel:{tel}">{phone_s}</a></p>' if tel else ''}
    </div>
  </div>
  {map_html}
</div></section>

<section id="claim"><div class="wrap">
  <p class="kicker">Make it real</p>
  <hr class="hairline">
  <h2>Want this live on your domain?</h2>
  <p><strong>${PRICE_USD}</strong> one-time — we finish your menu, hours, and photos.</p>
  <p><strong>Care ${CARE_MONTHLY_USD}/mo</strong> (or <strong>${CARE_YEARLY_USD}/yr</strong>) —
     hosting, SSL, monitoring, and small menu/hours tweaks so it stays live.</p>
  <p class="price">${PRICE_USD} builds it. Care keeps it live. Reply to claim.</p>
  <p>This sample was built for {name_s} at no cost, and nothing is published.
     Reply to the email that brought you here. Every email has a one-click opt-out.</p>
</div></section>
</main>

<div class="wrap">
  <p class="note">This is a free unpublished sample. Sample content is marked as such.
  Business name, address, phone, rating, and hours (when shown) come from public
  Google Places data. Hours are left off when we do not have them — we do not invent them.
  Not affiliated with or endorsed by {name_s}.</p>
  <footer>
    <span>© {year} {name_s}</span>
    <span>Unpublished sample · {datetime.now().strftime('%b %d, %Y')}</span>
  </footer>
</div>
{f'<a class="callbar" href="tel:{tel}">Call {phone_s}</a>' if tel else ''}
</body></html>""", token


if __name__ == "__main__":
    from pathlib import Path
    samples = [
        ("Simply Phở", "2929 Milam Street, Houston, TX",
         "(713) 555-0101", "restaurant", 4.6, "houston"),
        ("Melange Creperie", "1 Main St, Houston, TX",
         "(713) 555-0102", "restaurant", 4.5, "houston"),
        ("Revolucion Coffee", "2 Main St, Houston, TX",
         "(713) 555-0103", "cafe", 4.7, "houston"),
        ("Via313", "3 Main St, Houston, TX",
         "(713) 555-0104", "restaurant", 4.4, "houston"),
        ("Cream Parlor", "4 Main St, Houston, TX",
         "(713) 555-0105", "cafe", 4.8, "houston"),
        ("Taqueria La Esquina", "1234 Navigation Blvd, Houston, TX",
         "(713) 555-0142", "restaurant", 4.6, "houston"),
        ("East End Barber Co.", "401 Navigation Blvd, Houston, TX",
         "(713) 555-0118", "barber", 4.9, "houston"),
    ]
    out = Path(__file__).parent / "demos"
    out.mkdir(exist_ok=True)
    for args in samples:
        h, t = generate_site(*args, 1, 1, use_ai=False)
        p = out / f"sample-{args[3]}-{t}.html"
        p.write_text(h)
        print(f"wrote {p}")
