"""
Proposal emails via Resend.

This sends commercial email to businesses that did not ask for it, which in the
US means CAN-SPAM applies. The law is short and cheap to comply with, and the
penalties are per-email, so compliance is built into send_proposal() rather than
left to the caller:

  * accurate From / Reply-To, no deceptive subject line
  * clear disclosure that it's an unsolicited offer
  * a working one-click opt-out (List-Unsubscribe + visible link)
  * a real postal address
  * suppression list checked before every send, honored permanently

If SENDER_POSTAL_ADDRESS is unset, sending is refused — that's a required field,
not a nice-to-have.
"""

import html
import json
import urllib.error
import urllib.request

import db
from config import (FROM_EMAIL, FROM_NAME, PRICE_USD, RESEND_API_KEY, REPLY_TO,
                    SENDER_POSTAL_ADDRESS, UNSUBSCRIBE_BASE)

RESEND_URL = "https://api.resend.com/emails"


def unsubscribe_url(email: str) -> str:
    from urllib.parse import quote
    return f"{UNSUBSCRIBE_BASE}/unsubscribe?e={quote(email)}"


def build_email(business_name: str, demo_url: str, owner_email: str,
                category: str = "business", city: str = "", reply_to: str = "") -> tuple[str, str, str]:
    """Returns (subject, html_body, text_body)."""
    e = lambda s: html.escape(str(s or ""))
    name, cat = e(business_name), e(category or "business")
    unsub = unsubscribe_url(owner_email)
    reply_to = reply_to.strip() or REPLY_TO

    subject = f"A sample website for {business_name} (free, nothing published)"

    text = f"""Hi — I build simple websites for local {cat}s{f' in {city.title()}' if city else ''}.

I noticed {business_name} doesn't have a website yet, so I built you a sample one
to look at. It's free, it isn't published anywhere, and there's no obligation:

{demo_url}

If you like it, I'll put your real menu, hours and photos on it and set it up on
your own domain for a one-time ${PRICE_USD}. No subscription, no contract.
If it's not for you, just ignore this — or use the link below and I won't email again.

{FROM_NAME}
{f'Reply to: {reply_to}' if reply_to else ''}

---
This is an unsolicited business proposal sent to a publicly listed business address.
Opt out permanently: {unsub}
{SENDER_POSTAL_ADDRESS}
"""

    body = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f5">
<div style="max-width:560px;margin:0 auto;padding:32px 24px;font-family:-apple-system,
BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#1a1a1a;line-height:1.62">
  <p style="margin:0 0 16px">Hi — I build simple websites for local {cat}s{f" in {e(city.title())}" if city else ""}.</p>

  <p style="margin:0 0 16px">I noticed <b>{name}</b> doesn't have a website yet, so I built you a
  sample one to look at. It's free, it isn't published anywhere, and there's no obligation.</p>

  <p style="margin:24px 0"><a href="{e(demo_url)}"
    style="background:#1a1410;color:#e8b04b;padding:13px 28px;border-radius:6px;
    text-decoration:none;font-weight:600;display:inline-block">See your sample site</a></p>

  <p style="margin:0 0 16px">If you like it, I'll add your real menu, hours and photos and set it
  up on your own domain for a one-time <b>${PRICE_USD}</b> — no subscription, no contract.</p>

  <p style="margin:0 0 24px">If it's not for you, just ignore this email.</p>

  <p style="margin:0 0 4px">— {e(FROM_NAME)}</p>
  {f'<p style="margin:0 0 24px;color:#666">Reply directly to this email: {e(reply_to)}</p>' if reply_to else ''}

  <hr style="border:none;border-top:1px solid #ddd;margin:28px 0 16px">
  <p style="margin:0 0 8px;font-size:12px;color:#777">
    This is an unsolicited business proposal sent to a publicly listed business address.
    You can <a href="{e(unsub)}" style="color:#777">opt out permanently</a> and you won't be
    contacted again.
  </p>
  <p style="margin:0;font-size:12px;color:#777">{e(SENDER_POSTAL_ADDRESS)}</p>
</div></body></html>"""

    return subject, body, text


def send_proposal(business_name: str, demo_url: str, owner_email: str,
                  category: str = "business", city: str = "", lead_id=None, reply_to: str = ""):
    """Returns provider message id on success, None on failure/refusal."""
    owner_email = (owner_email or "").strip()

    if not RESEND_API_KEY:
        print("! RESEND_API_KEY not set")
        return None
    if not owner_email or "@" not in owner_email:
        print("! invalid recipient")
        return None
    if not SENDER_POSTAL_ADDRESS:
        print("! SENDER_POSTAL_ADDRESS is empty — required in commercial email (CAN-SPAM). "
              "Set it in .env before sending.")
        return None
    if db.is_suppressed(owner_email):
        print(f"! {owner_email} opted out previously — not sending")
        return None

    subject, body, text = build_email(business_name, demo_url, owner_email, category, city, reply_to)
    payload = {
        "from": f"{FROM_NAME} <{FROM_EMAIL}>",
        "to": [owner_email],
        "subject": subject,
        "html": body,
        "text": text,
        # One-click unsubscribe: required by Gmail/Yahoo bulk-sender rules and
        # it keeps you out of the spam folder.
        "headers": {
            "List-Unsubscribe": f"<{unsubscribe_url(owner_email)}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }
    effective_reply_to = reply_to.strip() or REPLY_TO
    if effective_reply_to:
        payload["reply_to"] = effective_reply_to

    req = urllib.request.Request(
        RESEND_URL, json.dumps(payload).encode(),
        {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        mid = data.get("id")
        db.log_email(lead_id, owner_email, subject, mid, "sent")
        print(f"sent to {owner_email} (id {mid})")
        return mid
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        print(f"! Resend {e.code}: {detail}")
        db.log_email(lead_id, owner_email, subject, None, f"error {e.code}")
        return None
    except Exception as ex:
        print(f"! send failed: {ex}")
        db.log_email(lead_id, owner_email, subject, None, "error")
        return None


if __name__ == "__main__":
    s, h, t = build_email("Taqueria La Esquina", "http://localhost:8080/demo/abc123",
                          "owner@example.com", "restaurant", "houston")
    print("SUBJECT:", s)
    print(t)
