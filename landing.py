"""Marketing homepage for restaurant-ai-bot.

Copy is Foundry Growth + Chief of Staff: short hero is the default
(especially on mobile). Longer Growth lines show only when the layout
has room. How-it-works beats stay verbatim.
"""

import html
from urllib.parse import quote

from config import FROM_EMAIL, REPLY_TO

# Resend's sandbox default is not a real inbox — never use it as a CTA.
_PLACEHOLDER_FROM = "onboarding@resend.dev"

HEADLINE_SHORT = "No website? We’ll build one."
HEADLINE_LONG = "No website? We’ll build you one."
SUB = (
    "For local businesses stuck on Facebook, Instagram, or a Google "
    "listing. Clean site customers can use tonight."
)
CTA_SHORT = "Get free preview"
CTA_LONG = "Get my free site preview"
CTA_SECONDARY = "How it works"
ONE_LINER = "We build websites for local businesses that don’t have one yet."
PRICE_LINE = (
    "$99 builds the site. Care ($29/mo or $249/yr) keeps it online with hosting, "
    "SSL, and small updates. No surprise subscription on the build."
)
PRICE_ONE_LINER = "$99 gets the site. Care keeps it live."
EMPTY_SITES = (
    "No sites yet. Point us at a shop without a website and we’ll draft one."
)
HOW_IT_WORKS = (
    ("We find you", "restaurants and shops without a real site"),
    ("We build a preview", "name, menu/hours, photos, call/directions"),
    ("You approve", "go live or tweak; pay when you’re happy"),
)


def preview_contact_email() -> str:
    """Public request-preview address from config only. Never invent one."""
    reply = (REPLY_TO or "").strip()
    if reply and "@" in reply:
        return reply
    from_addr = (FROM_EMAIL or "").strip()
    if from_addr and "@" in from_addr and from_addr.lower() != _PLACEHOLDER_FROM:
        return from_addr
    return ""


def _cta_href(contact_email: str) -> str:
    if not contact_email:
        return "#preview"
    subject = quote("Free site preview")
    body = quote("Restaurant name:\nCity:\nHow to reach you:\n")
    return f"mailto:{contact_email}?subject={subject}&body={body}"


def render_home(contact_email: str = "", sites=None) -> bytes:
    email = (contact_email or "").strip()
    # Hero CTA scrolls to the form — never put mailto/email on this <a>
    # (some reviewers concatenate mailto address onto the visible label).
    href = "#preview"
    cta_label = html.escape(CTA_SHORT)
    cta_aria = html.escape(CTA_SHORT, quote=True)
    email_safe = html.escape(email)
    empty = sites == 0
    empty_block = (
        f'<p class="empty" role="status">{html.escape(EMPTY_SITES)}</p>'
        if empty
        else ""
    )
    if email:
        form_action = f"mailto:{email_safe}"
        form_note = (
            "Opens your email app to request a free preview. "
            "Nothing is posted to this server."
        )
        form_method = "post"
        form_enctype = ' enctype="text/plain"'
    else:
        form_action = "#preview"
        form_note = (
            "No public inbox is configured on this deployment. "
            "This form stays on the page and does not send data to a server. "
            "If we already emailed you a preview, reply there."
        )
        form_method = "get"
        form_enctype = ""

    beats = []
    for i, (title, detail) in enumerate(HOW_IT_WORKS, start=1):
        beats.append(
            f'<li class="beat">'
            f'<span class="num" aria-hidden="true">{i:02d}</span>'
            f"<h3>{html.escape(title)}</h3>"
            f"<p>{html.escape(detail)}</p>"
            f"</li>"
        )
    beats_html = "".join(beats)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(HEADLINE_SHORT)}</title>
<meta name="description" content="{html.escape(SUB)}">
<meta property="og:title" content="{html.escape(HEADLINE_SHORT)}">
<meta property="og:description" content="{html.escape(ONE_LINER)}">
<style>
:root {{
  --ink: #1a1410;
  --paper: #f6f1e8;
  --paper-2: #efe6d6;
  --gold: #c48a2a;
  --gold-deep: #9a6c1c;
  --muted: #5c5348;
  --line: rgba(26,20,16,.12);
  --shadow: 0 18px 40px rgba(26,20,16,.08);
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
@media (prefers-reduced-motion: reduce) {{
  html {{ scroll-behavior: auto; }}
}}
body {{
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(1200px 480px at 10% -10%, #fff8ec 0%, transparent 55%),
    var(--paper);
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
  line-height: 1.55;
}}
a {{ color: inherit; }}
.wrap {{
  width: min(1080px, calc(100% - 40px));
  margin: 0 auto;
}}
.skip {{
  position: absolute; left: -999px; top: 8px;
}}
.skip:focus {{
  left: 12px; background: var(--ink); color: var(--paper);
  padding: 8px 12px; z-index: 10;
}}
header.nav {{
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 22px 0 8px;
}}
.brand {{
  font-size: 13px; letter-spacing: .16em; text-transform: uppercase;
  font-weight: 600;
}}
.tag {{
  display: none; color: var(--muted); font-size: 14px; max-width: 42ch;
}}
.hero {{
  padding: 48px 0 28px;
}}
.kicker {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 12px; letter-spacing: .22em; text-transform: uppercase;
  color: var(--gold-deep); margin: 0 0 14px;
}}
h1 {{
  font-size: clamp(2.15rem, 8vw, 4.4rem);
  line-height: 1.05; font-weight: 500; letter-spacing: -.03em;
  margin: 0 0 18px; max-width: 14ch;
}}
.extra {{ display: none; }}
.sub {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 1.05rem; color: var(--muted); max-width: 38rem;
  margin: 0 0 28px;
}}
.price-line {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 14px; color: var(--muted); max-width: 42rem; margin: 16px 0 0;
}}
.ctas {{
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
}}
.btn {{
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 48px; padding: 0 22px; border-radius: 999px;
  text-decoration: none; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 15px; font-weight: 600;
}}
.btn.primary {{
  background: var(--ink); color: #f6e7c4;
}}
.btn.ghost {{
  border: 1px solid var(--ink); background: transparent;
}}
.btn:focus-visible, input:focus-visible, textarea:focus-visible {{
  outline: 3px solid var(--gold); outline-offset: 2px;
}}
.empty {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--paper-2); border: 1px solid var(--line);
  padding: 14px 16px; border-radius: 12px; margin: 22px 0 0; max-width: 40rem;
}}
.how {{
  padding: 28px 0 56px;
}}
.how h2 {{
  font-size: clamp(1.6rem, 4vw, 2.2rem); font-weight: 500; margin: 0 0 22px;
}}
.beats {{
  list-style: none; margin: 0; padding: 0;
  display: grid; gap: 14px;
}}
.beat {{
  background: #fffdf8; border: 1px solid var(--line);
  border-radius: 16px; padding: 22px 22px 20px; box-shadow: var(--shadow);
}}
.num {{
  display: block; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 12px; letter-spacing: .18em; color: var(--gold-deep); margin-bottom: 8px;
}}
.beat h3 {{ margin: 0 0 6px; font-size: 1.25rem; font-weight: 550; }}
.beat p {{ margin: 0; color: var(--muted);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}}
.preview {{
  padding: 8px 0 64px;
}}
.card {{
  background: var(--ink); color: #f6f1e8; border-radius: 20px;
  padding: 28px 24px; box-shadow: var(--shadow);
}}
.card h2 {{ margin: 0 0 8px; font-size: 1.7rem; font-weight: 500; }}
.card .lede {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: #d9cbb6; margin: 0 0 20px;
}}
label {{
  display: block; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 13px; margin: 0 0 6px;
}}
.field {{ margin: 0 0 14px; }}
input, textarea {{
  width: 100%; border: 1px solid rgba(246,241,232,.22); background: #261e18;
  color: #f6f1e8; border-radius: 10px; padding: 12px 12px; font: inherit;
}}
.card .btn.primary {{ background: #e8b04b; color: #1a1410; border: 0; cursor: pointer; }}
.note {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 13px; color: #cfc3b0; margin: 14px 0 0;
}}
footer {{
  border-top: 1px solid var(--line); padding: 22px 0 36px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: var(--muted); font-size: 14px;
}}
.demo-note {{ margin: 8px 0 0; }}
@media (min-width: 720px) {{
  .tag {{ display: block; }}
  .hero {{ padding: 72px 0 40px; }}
  h1 {{ max-width: 16ch; }}
  .extra {{ display: inline; }}
  .beats {{ grid-template-columns: repeat(3, 1fr); gap: 18px; }}
  .card {{ padding: 36px 40px; display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: start; }}
}}
</style>
</head>
<body>
<a class="skip" href="#how-it-works">Skip to how it works</a>
<header class="nav wrap">
  <div class="brand">Local Web Studio</div>
  <p class="tag">{html.escape(ONE_LINER)}</p>
</header>
<main>
  <section class="hero wrap">
    <p class="kicker">Restaurants &amp; local shops</p>
    <h1>No website? We’ll build <span class="extra">you </span>one.</h1>
    <p class="sub">{html.escape(SUB)}</p>
    <div class="ctas">
      <a class="btn primary" href="{href}" aria-label="{cta_aria}">{cta_label}</a>
      <a class="btn ghost" href="#how-it-works">{html.escape(CTA_SECONDARY)}</a>
    </div>
    <p class="price-line">{html.escape(PRICE_ONE_LINER)} {html.escape(PRICE_LINE)}</p>
    {empty_block}
  </section>
  <section class="how wrap" id="how-it-works">
    <h2>How it works</h2>
    <ol class="beats">{beats_html}</ol>
  </section>
  <section class="preview wrap" id="preview">
    <div class="card">
      <div>
        <h2>Request a preview</h2>
        <p class="lede">Point us at a shop without a website and we’ll draft one.</p>
      </div>
      <form action="{form_action}" method="{form_method}"{form_enctype}>
        <div class="field">
          <label for="biz">Restaurant or shop</label>
          <input id="biz" name="business" type="text" autocomplete="organization" required>
        </div>
        <div class="field">
          <label for="city">City</label>
          <input id="city" name="city" type="text" autocomplete="address-level2">
        </div>
        <div class="field">
          <label for="reach">How to reach you</label>
          <input id="reach" name="reach" type="text" autocomplete="email" placeholder="Email or phone">
        </div>
        <button class="btn primary" type="submit">{html.escape(CTA_SHORT)}</button>
        <p class="note">{form_note}</p>
      </form>
    </div>
  </section>
</main>
<footer class="wrap">
  <p>{html.escape(ONE_LINER)}</p>
  <p class="demo-note">If we already built you a preview, it lives at a private <code>/demo/&lt;token&gt;</code> link we sent you — we don’t list those here.</p>
</footer>
</body>
</html>""".encode()
