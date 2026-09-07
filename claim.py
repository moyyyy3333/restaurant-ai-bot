"""Stripe Checkout stub for the $99 build + optional Care plan.

Renders and returns structured responses without live keys so /ops and
/claim/* can deploy. When STRIPE_SECRET_KEY is set, creates a real
Checkout Session via Stripe's HTTP API (stdlib urllib — no stripe SDK).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from html import escape

from config import (
    BUILD_PRICE_USD,
    CARE_MONTHLY_USD,
    CARE_YEARLY_USD,
    DEMO_BASE_URL,
    SALES_SMS_NUMBER,
    STRIPE_PRICE_BUILD,
    STRIPE_PRICE_CARE_MONTHLY,
    STRIPE_PRICE_CARE_YEARLY,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)

CARE_PLANS = ("none", "monthly", "yearly")


def pricing() -> dict:
    return {
        "build": {
            "amount_usd": BUILD_PRICE_USD,
            "interval": "one_time",
            "label": "Website build",
        },
        "care_monthly": {
            "amount_usd": CARE_MONTHLY_USD,
            "interval": "month",
            "label": "Care",
        },
        "care_yearly": {
            "amount_usd": CARE_YEARLY_USD,
            "interval": "year",
            "label": "Care (annual)",
        },
    }


def stripe_configured() -> bool:
    key = (STRIPE_SECRET_KEY or "").strip()
    return key.startswith(("sk_", "rk_"))


def normalize_care(care: str | None) -> str:
    c = (care or "none").strip().lower()
    return c if c in CARE_PLANS else "none"


def amount_cents(care: str) -> int:
    total = BUILD_PRICE_USD * 100
    care = normalize_care(care)
    if care == "monthly":
        total += CARE_MONTHLY_USD * 100
    elif care == "yearly":
        total += CARE_YEARLY_USD * 100
    return total


def line_items_preview(care: str) -> list[dict]:
    items = [{"label": "Website build", "amount_usd": BUILD_PRICE_USD, "interval": "one_time"}]
    care = normalize_care(care)
    if care == "monthly":
        items.append({"label": "Care", "amount_usd": CARE_MONTHLY_USD, "interval": "month"})
    elif care == "yearly":
        items.append({"label": "Care (annual)", "amount_usd": CARE_YEARLY_USD, "interval": "year"})
    return items


def stub_checkout_url(demo_token: str, care: str = "none") -> str:
    care = normalize_care(care)
    return f"/claim/stub?t={urllib.parse.quote(demo_token or '')}&care={care}"


def start_url(demo_token: str, care: str = "none") -> str:
    care = normalize_care(care)
    return f"/claim/start?t={urllib.parse.quote(demo_token or '')}&care={care}"


def create_checkout(lead: dict, care: str = "none") -> dict:
    """Start Checkout for a lead. Always returns a dict; never raises to the UI.

    {ok, stub, url, session_id, line_items, pricing, error}
    """
    care = normalize_care(care)
    items = line_items_preview(care)
    token = lead.get("demo_token") or ""
    payload = {
        "ok": True,
        "stub": not stripe_configured(),
        "url": stub_checkout_url(token, care),
        "session_id": None,
        "line_items": items,
        "pricing": pricing(),
        "care_plan": care,
        "lead_id": lead.get("id"),
        "amount_cents": amount_cents(care),
        "error": None,
    }
    if payload["stub"]:
        payload["message"] = (
            "Stripe keys are not set. Opening the checkout placeholder. "
            "Set STRIPE_SECRET_KEY to create a live Checkout Session."
        )
        return payload

    success = f"{DEMO_BASE_URL}/claim/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel = f"{DEMO_BASE_URL}/claim/cancel?t={urllib.parse.quote(token)}"
    session = _create_stripe_session(lead, care, success, cancel)
    if session.get("id") and session.get("url"):
        payload["url"] = session["url"]
        payload["session_id"] = session["id"]
        payload["stub"] = False
        return payload
    err = (session.get("error") or {}).get("message") if isinstance(session.get("error"), dict) else session.get("error")
    payload["ok"] = False
    payload["error"] = err or "stripe_session_failed"
    payload["stub"] = False
    payload["url"] = None
    payload["message"] = "Stripe Checkout is temporarily unavailable. Please try again."
    return payload


def _flatten(prefix, obj, out: dict):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}[{k}]", v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten(f"{prefix}[{i}]", v, out)
    elif obj is not None:
        out[prefix] = str(obj)


def _line_item(price_id: str, fallback_name: str, amount_usd: int, recurring: str | None):
    if price_id:
        return {"price": price_id, "quantity": 1}
    price_data = {
        "currency": "usd",
        "unit_amount": amount_usd * 100,
        "product_data": {"name": fallback_name},
    }
    if recurring:
        price_data["recurring"] = {"interval": recurring}
    return {"price_data": price_data, "quantity": 1}


def _create_stripe_session(lead: dict, care: str, success_url: str, cancel_url: str) -> dict:
    items = [_line_item(STRIPE_PRICE_BUILD, "Website build", BUILD_PRICE_USD, None)]
    mode = "payment"
    if care == "monthly":
        items.append(_line_item(STRIPE_PRICE_CARE_MONTHLY, "Care", CARE_MONTHLY_USD, "month"))
        mode = "subscription"
    elif care == "yearly":
        items.append(_line_item(STRIPE_PRICE_CARE_YEARLY, "Care (annual)", CARE_YEARLY_USD, "year"))
        mode = "subscription"

    form: dict = {}
    _flatten("line_items", items, form)
    form["mode"] = mode
    form["success_url"] = success_url
    form["cancel_url"] = cancel_url
    form["client_reference_id"] = str(lead.get("id") or "")
    form["metadata[lead_id]"] = str(lead.get("id") or "")
    form["metadata[care_plan]"] = care
    form["metadata[demo_token]"] = lead.get("demo_token") or ""
    name = lead.get("name") or "Local business"
    form["metadata[business]"] = name
    form["phone_number_collection[enabled]"] = "true"
    if mode == "payment":
        form["customer_creation"] = "always"
        form["payment_intent_data[metadata][lead_id]"] = str(lead.get("id") or "")
        form["payment_intent_data[metadata][demo_token]"] = lead.get("demo_token") or ""
    else:
        form["subscription_data[metadata][lead_id]"] = str(lead.get("id") or "")
        form["subscription_data[metadata][care_plan]"] = care
        form["subscription_data[metadata][demo_token]"] = lead.get("demo_token") or ""

    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=body,
        headers={
            "Authorization": f"Bearer {STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error": {"message": raw or f"http_{e.code}"}}
    except Exception as e:
        return {"error": {"message": str(e)}}


def verify_webhook(payload: bytes, sig_header: str) -> bool:
    """Verify Stripe-Signature when STRIPE_WEBHOOK_SECRET is set. Otherwise False."""
    secret = (STRIPE_WEBHOOK_SECRET or "").strip()
    if not secret or not sig_header:
        return False
    try:
        import hmac
        import hashlib
        parts = [p.split("=", 1) for p in sig_header.split(",") if "=" in p]
        timestamp = next((v for k, v in parts if k == "t"), "")
        signatures = [v for k, v in parts if k == "v1"]
        if not timestamp or abs(time.time() - int(timestamp)) > 300:
            return False
        signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
        digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(digest, signature) for signature in signatures)
    except Exception:
        return False


def _shell(title: str, body: str) -> bytes:
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ --bg:#f3efe6; --ink:#1c1916; --mut:#6f6a62; --card:#fff; --acc:#c45c2a; --line:#e4ddd0; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  min-height:100vh; display:flex; align-items:center; justify-content:center; padding:28px; }}
.box {{ max-width:520px; width:100%; background:var(--card); border:1px solid var(--line);
  border-radius:14px; padding:36px 32px; box-shadow:0 8px 24px rgba(40,30,10,.06); }}
.k {{ font:11px ui-monospace,Menlo,monospace; letter-spacing:.16em; text-transform:uppercase; color:var(--acc); }}
h1 {{ font-size:26px; margin:10px 0 8px; }}
p {{ color:#4a453e; margin:0 0 12px; }}
.price {{ font-size:22px; font-weight:700; margin:18px 0 6px; }}
.item {{ display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--line); }}
.muted {{ color:var(--mut); font-size:13px; }}
a.btn {{ display:inline-block; margin-top:18px; background:var(--acc); color:#fff; text-decoration:none;
  padding:12px 20px; border-radius:8px; font-weight:600; }}
</style></head><body><div class="box">{body}</div></body></html>""".encode()


def inject_claim_bar(html: str, business_name: str, demo_token: str) -> str:
    """Add buyer checkout controls without changing the generated site body."""
    name = escape(business_name or "this business")
    token = urllib.parse.quote(demo_token or "")
    bar = f"""
<style id="preview-claim-style">
body{{padding-bottom:max(7.25rem,env(safe-area-inset-bottom))!important}}
.preview-claim{{position:fixed;z-index:2147483000;left:.65rem;right:.65rem;bottom:.65rem;
font:500 14px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#181512;
background:rgba(255,253,248,.97);border:1px solid rgba(24,21,18,.16);border-radius:14px;
box-shadow:0 12px 36px rgba(0,0,0,.2);padding:.75rem;backdrop-filter:blur(12px)}}
.preview-claim__row{{display:flex;flex-wrap:wrap;align-items:center;gap:.55rem}}
.preview-claim__copy{{flex:1 1 17rem}}.preview-claim__copy strong{{display:block;font-size:15px}}
.preview-claim__actions{{display:flex;flex:1 1 18rem;gap:.45rem}}
.preview-claim__button{{display:inline-flex;flex:1;min-height:42px;align-items:center;
justify-content:center;border-radius:9px;padding:.55rem .7rem;text-decoration:none!important;
font-weight:700;background:#181512;color:#fff!important;border:1px solid #181512}}
.preview-claim__button--care{{background:transparent;color:#181512!important}}
.preview-claim details{{margin-top:.4rem;font-size:12px;color:#59524a}}
.preview-claim summary{{cursor:pointer;width:max-content}}
@media(min-width:760px){{.preview-claim{{left:50%;right:auto;transform:translateX(-50%);
width:min(880px,calc(100% - 2rem));padding:.7rem .9rem}}body{{padding-bottom:6rem!important}}}}
</style>
<aside class="preview-claim" aria-label="Claim this website preview">
  <div class="preview-claim__row">
    <div class="preview-claim__copy"><strong>This is a preview built for {name}.</strong>
      Make it yours — ${BUILD_PRICE_USD} one-time, optional Care ${CARE_MONTHLY_USD}/mo.</div>
    <div class="preview-claim__actions">
      <a class="preview-claim__button" href="/claim/start?t={token}&amp;care=none">Claim this site</a>
      <a class="preview-claim__button preview-claim__button--care"
         href="/claim/start?t={token}&amp;care=monthly">Claim with Care</a>
    </div>
  </div>
  <details><summary>What you get</summary>
    Hosting, mobile layout, Google Maps, click-to-call, edits for 30 days, and a target launch within 48 hours.
  </details>
</aside>"""
    marker = "</body>"
    return html.replace(marker, bar + marker, 1) if marker in html else html + bar


def render_stub(lead: dict | None, care: str = "none") -> bytes:
    care = normalize_care(care)
    name = escape((lead or {}).get("name") or "Your business")
    rows = []
    for i in line_items_preview(care):
        suffix = f" / {i['interval']}" if i["interval"] != "one_time" else ""
        rows.append(
            f'<div class="item"><span>{escape(i["label"])}{escape(suffix)}</span>'
            f'<b>${i["amount_usd"]}</b></div>'
        )
    items = "".join(rows)
    care_note = {
        "none": "Build only — add Care at $29/mo or $249/yr when Stripe is live.",
        "monthly": "Build + Care billed monthly.",
        "yearly": "Build + Care billed annually.",
    }[care]
    return _shell("Claim checkout (stub)", f"""
      <div class="k">Checkout placeholder</div>
      <h1>Claim {name}</h1>
      <p>One-time website build is <b>${BUILD_PRICE_USD}</b>. Optional Care is
      ${CARE_MONTHLY_USD}/mo or ${CARE_YEARLY_USD}/yr.</p>
      {items}
      <p class="muted" style="margin-top:14px">{escape(care_note)}</p>
      <p class="muted">Stripe is not configured on this deployment
      (<code>STRIPE_SECRET_KEY</code>). This page is the UI stub — the operator
      marks the lead <b>claimed</b> from <code>/ops</code> after payment lands.
      Live Checkout will use the same $99 + Care amounts.</p>
    """)


def render_success(session_id: str = "", claim_record: dict | None = None) -> bytes:
    sid = escape(session_id or "")
    extra = f'<p class="muted">Session <code>{sid}</code></p>' if sid else ""
    claim_token = (claim_record or {}).get("claim_token") or ""
    onboard = (
        f'<a class="btn" href="/onboard/{escape(claim_token)}">Start onboarding</a>'
        if claim_token
        else '<p class="muted">Your private onboarding link is also in your welcome email.</p>'
    )
    sms = (
        f'<p><a href="sms:{escape(SALES_SMS_NUMBER)}">Text us with a question</a></p>'
        if SALES_SMS_NUMBER
        else ""
    )
    return _shell("You're in", f"""
      <div class="k">Payment received</div>
      <h1>Your site is moving toward launch.</h1>
      <p>Next, confirm your hours, contact details, menu, photos, and domain.
      We review those details and target going live within 48 hours.</p>
      <p>If you added Care, hosting, SSL, monitoring, and small updates are
      included while the plan is active.</p>
      {onboard}
      {sms}
      {extra}
    """)


def render_cancel(demo_token: str = "") -> bytes:
    retry = f"/claim/start?t={urllib.parse.quote(demo_token)}" if demo_token else "/"
    return _shell("Checkout canceled", f"""
      <div class="k">No charge</div>
      <h1>Checkout canceled</h1>
      <p>Nothing was billed. You can restart the ${BUILD_PRICE_USD} claim
      whenever you're ready.</p>
      <a class="btn" href="{escape(retry)}">Try again</a>
    """)
