"""Stripe Checkout stub for the $99 build + optional Care plan.

Renders and returns structured responses without live keys so /ops and
/claim/* can deploy. When STRIPE_SECRET_KEY is set, creates a real
Checkout Session via Stripe's HTTP API (stdlib urllib — no stripe SDK).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from html import escape

from config import (
    BUILD_PRICE_USD,
    CARE_MONTHLY_USD,
    CARE_YEARLY_USD,
    DEMO_BASE_URL,
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
    return key.startswith("sk_")


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
    payload["stub"] = True
    payload["url"] = stub_checkout_url(token, care)
    payload["message"] = "Stripe Checkout failed; falling back to the placeholder."
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
        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
        timestamp = parts.get("t", "")
        expected = parts.get("v1", "")
        signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
        digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, expected)
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


def render_success(session_id: str = "") -> bytes:
    sid = escape(session_id or "")
    extra = f'<p class="muted">Session <code>{sid}</code></p>' if sid else ""
    return _shell("You're in", f"""
      <div class="k">Claim received</div>
      <h1>Thanks — we'll take it from here.</h1>
      <p>The ${BUILD_PRICE_USD} build is next. If you added Care, hosting and
      small updates are included on that plan.</p>
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
