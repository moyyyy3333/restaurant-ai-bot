"""
Demo server.

  /                     marketing homepage (HTML)
  /stats                health + counts (former GET / JSON)
  /health               process health (always 200 if the function is up)
  /demo/<token>         serve a generated sample site (expires)
  /ops                  token-gated operator board (Prospect Board layout)
  /claim/start          Stripe Checkout (or stub) for $99 build + optional Care
  /unsubscribe?e=...    one-click opt-out (GET renders, POST confirms)
  /webhook/resend       inbound reply/bounce events -> lead status
  /webhook/stripe       Checkout completed -> claimed (needs STRIPE_WEBHOOK_SECRET)
  /pipeline/run         token-guarded: full daily scan -> site -> email -> send

Stdlib only — no Flask needed, so `python server.py` just works.

On Vercel the Handler class is invoked per request and main() never runs, so
schema setup happens in ensure_schema() on the first request.
"""

import json
import os
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import claim
import db
import ops
from config import DAILY_SEND_LIMIT, DEFAULT_CITIES, DEMO_BASE_URL, DEMO_EXPIRE_HOURS, PORT
from landing import preview_contact_email, render_home

LEAD_STATUSES = ops.LEAD_STATUSES

PIPELINE_TOKEN = os.getenv("PIPELINE_TOKEN", "")


BOARD_KEY = (os.getenv("BOARD_KEY") or os.getenv("PIPELINE_TOKEN") or "").strip()


def board_payload() -> dict:
    """Everything the Prospect Board needs in one call. ponytail: one query set, no caching."""
    from datetime import date
    import config as C
    cities = list(C.CITIES.keys())
    cats = list(C.BUSINESS_CATEGORIES.keys())
    doy = date.today().timetuple().tm_yday
    stats = db.get_stats()
    with db.conn() as c:
        leads = [dict(r) for r in c.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 200").fetchall()]
        research = [dict(r) for r in c.execute(
            "SELECT id, name, city, phone FROM leads WHERE (email IS NULL OR email = '') "
            "AND status NOT IN ('dead','sold') ORDER BY id DESC LIMIT 50").fetchall()]
        log = [dict(r) for r in c.execute(
            "SELECT created_at, to_email, subject, status FROM email_log ORDER BY id DESC LIMIT 40").fetchall()]
        qc = {
            "new": c.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0],
            "need_site": c.execute("SELECT COUNT(*) FROM leads WHERE status='new' AND (demo_token IS NULL OR demo_token='')").fetchone()[0],
            "need_send": c.execute("SELECT COUNT(*) FROM leads WHERE status='site_generated' AND emailed=0").fetchone()[0],
        }
    for l in leads:
        l["demo_url"] = f"{DEMO_BASE_URL}/demo/{l['demo_token']}" if l.get("demo_token") else None
        for k in ("business_id",):
            l.pop(k, None)
    entries = [{"when": (x.get("created_at") or "")[:16], "what": f"email {x.get('status') or ''} -> {x.get('to_email') or ''} · {x.get('subject') or ''}"} for x in log]
    for l in leads:
        if l.get("notes"):
            for line in str(l["notes"]).splitlines():
                entries.append({"when": line[1:17] if line.startswith("[") else "", "what": f"{l['name']}: {line[19:] if line.startswith('[') else line}"})
    entries.sort(key=lambda e: e["when"], reverse=True)
    import config as CFG
    from_email = (CFG.FROM_EMAIL or "").strip()
    sending_ok = bool(CFG.RESEND_API_KEY) and not from_email.endswith("@resend.dev")
    return {
        "sending": {
            "ok": sending_ok,
            "from": from_email or "(unset)",
            "why": "" if sending_ok else
                   "Outreach email is OFF. FROM_EMAIL is still Resend's test address, which can only "
                   "deliver to the Resend account owner — not to business owners. Verify a sending "
                   "domain in Resend, then set FROM_EMAIL and RESEND_API_KEY.",
        },
        "today": {"city": cities[doy % len(cities)] if cities else "", "category": cats[doy % len(cats)] if cats else ""},
        "cities": cities, "categories": cats, "stats": stats, "queue_counts": qc,
        "leads": leads, "research": research, "log": entries[:60],
    }


def page(title: str, body: str) -> bytes:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
background:#f4f4f5;color:#1a1a1a;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;padding:24px}}.box{{max-width:520px;background:#fff;padding:40px;
border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}h1{{font-size:22px;margin:0 0 12px}}
p{{line-height:1.6;color:#555;margin:0 0 12px}}button{{background:#1a1410;color:#e8b04b;
border:0;padding:12px 26px;border-radius:6px;font-size:15px;cursor:pointer}}
code{{background:#f0f0f0;padding:2px 6px;border-radius:4px}}</style></head>
<body><div class="box">{body}</div></body></html>""".encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalBizBot/1.0"

    def log_message(self, fmt, *args):  # quieter logs
        print(f"  {self.address_string()} {fmt % args}")

    # ------------------------------------------------------------------ helpers
    def send(self, code: int, body: bytes, ctype="text/html; charset=utf-8",
             robots=True):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if robots:
            self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        self.wfile.write(body)

    def json_out(self, code: int, obj: dict):
        self.send(code, json.dumps(obj, default=str).encode(), "application/json")

    def _fail(self, err: Exception):
        print(f"  handler error: {type(err).__name__}: {err}")
        try:
            self.json_out(500, {"ok": False, "error": "internal_error"})
        except Exception:
            pass

    # ---------------------------------------------------------------------- GET
    def do_GET(self):
        try:
            db.ensure_schema()
            self._do_GET()
        except Exception as e:
            self._fail(e)

    def _do_GET(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]

        is_health = bool(parts) and (
            parts[0] == "health" or (parts[0] == "api" and len(parts) > 1 and parts[1] == "health")
        )
        if is_health:
            payload = {"ok": True, "service": "local-business-ai-bot", **db.db_status()}
            return self.json_out(200, payload)

        if not parts:
            sites = None
            try:
                sites = db.get_stats().get("sites")
            except Exception as e:
                print(f"  homepage stats failed: {e}")
            return self.send(200, render_home(preview_contact_email(), sites),
                             robots=False)

        if parts[0] == "board":
            if not self._board_ok(u):
                return self.send(403, page("Locked", "<h1>Locked</h1><p>Open the board from the bot with /help.</p>"))
            return self._send_repo_html("board.html", "Board", robots=False)

        if parts[0] == "ops":
            if not self._board_ok(u):
                return self.send(403, page("Locked",
                    "<h1>Locked</h1><p>Open <code>/ops?k=YOUR_PIPELINE_TOKEN</code> "
                    "(same secret as the Prospect Board).</p>"))
            return self._send_repo_html("ops.html", "Ops")

        if parts[0] == "api" and len(parts) > 1 and parts[1] == "board":
            if not self._board_ok(u):
                return self.json_out(403, {"error": "locked"})
            return self.json_out(200, board_payload())

        if parts[0] == "api" and len(parts) > 1 and parts[1] == "ops":
            if not self._board_ok(u):
                return self.json_out(403, {"error": "locked"})
            return self.json_out(200, ops.ops_payload())

        if parts[0] == "claim":
            return self.claim_get(parts, u)

        if parts[0] == "stats":
            payload = {"ok": True, "service": "local-business-ai-bot", **db.db_status()}
            try:
                payload.update(db.get_stats())
            except Exception as e:
                print(f"  homepage stats failed: {e}")
                payload["error"] = "stats_unavailable"
            return self.json_out(200, payload)

        if parts[0] == "demo" and len(parts) > 1:
            return self.serve_demo(parts[1])

        if parts[0] == "unsubscribe":
            email = (parse_qs(u.query).get("e") or [""])[0]
            if not email:
                return self.send(400, page("Opt out", "<h1>Missing address</h1>"))
            return self.send(200, page("Opt out", f"""
                <h1>Stop emails to {email}?</h1>
                <p>Confirm and you will not be contacted again. This is permanent.</p>
                <form method="POST" action="/unsubscribe">
                  <input type="hidden" name="e" value="{email}">
                  <button type="submit">Unsubscribe me</button>
                </form>"""))

        if parts[0] == "favicon.ico":
            return self.send(204, b"")

        return self.send(404, page("Not found", "<h1>Not found</h1>"))

    def rebuild_demo(self, lead, token: str) -> str:
        """Always rebuild from the current generator so design upgrades land
        on existing /demo/{token} links. Extends expiry on open."""
        from generator import generate_site
        html_str, _ = generate_site(
            name=lead["name"] or "Business",
            address=lead["address"] or "",
            phone=lead["phone"] or "",
            category=lead["category"] or "restaurant",
            rating=lead["rating"],
            city=lead["city"] or "",
            lead_id=lead["id"],
            business_id=lead["business_id"],
            use_ai=False,
            fetch_place=True,
        )
        try:
            db.save_demo_html(token, html_str)
        except Exception as e:
            print(f"  could not persist regenerated demo: {e}")
        try:
            db.update_lead(
                lead["id"],
                demo_expires_at=(datetime.now() + timedelta(hours=DEMO_EXPIRE_HOURS)).isoformat(),
            )
        except Exception as e:
            print(f"  could not extend demo expiry: {e}")
        db.bump_demo_views(token)
        return html_str

    def serve_demo(self, token: str):
        lead = db.get_lead_by_token(token)
        demo = db.get_demo(token)
        if not demo or not lead:
            return self.send(404, page("Expired", "<h1>This sample isn't available</h1>"
                                       "<p>The link may have expired.</p>"))
        # Rebuild on every open: stored HTML would freeze the old template, and
        # an expired token should come back instead of a 410 dead-end.
        return self.send(200, self.rebuild_demo(lead, token).encode())

    # --------------------------------------------------------------------- POST
    def do_POST(self):
        try:
            db.ensure_schema()
            self._do_POST()
        except Exception as e:
            self._fail(e)

    def _do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        if u.path == "/unsubscribe":
            email = (parse_qs(raw.decode()).get("e") or [""])[0]
            if email:
                db.suppress(email, "one-click unsubscribe")
                print(f"  opted out: {email}")
            return self.send(200, page("Done", "<h1>You're unsubscribed</h1>"
                                       "<p>You won't be contacted again. Sorry for the interruption.</p>"))

        if u.path == "/webhook/resend":
            return self.resend_webhook(raw)

        if u.path == "/api/lead":
            if not self._board_ok(u):
                return self.json_out(403, {"error": "locked"})
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self.json_out(400, {"error": "bad json"})
            lead_id = int(body.get("id") or 0)
            fields = {}
            if body.get("status") in LEAD_STATUSES:
                fields["status"] = body["status"]
                if body["status"] == "replied":
                    fields["replied"] = 1
                if body["status"] == "sold":
                    fields["sold"] = 1
                if body["status"] == "claimed":
                    fields["claimed"] = 1
                    fields["claimed_at"] = db.now()
            if isinstance(body.get("notes"), str) and body["notes"].strip():
                old_lead = db.get_lead(lead_id)
                prev = (old_lead["notes"] or "") if old_lead else ""
                fields["notes"] = (prev + "\n" if prev else "") + f"[{db.now()[:16]}] " + body["notes"].strip()
            if not lead_id or not fields:
                return self.json_out(400, {"error": "nothing to update"})
            db.update_lead(lead_id, **fields)
            return self.json_out(200, {"ok": True})

        if u.path == "/api/ops/meta":
            if not self._board_ok(u):
                return self.json_out(403, {"error": "locked"})
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self.json_out(400, {"error": "bad json"})
            if "notes" in body and isinstance(body.get("notes"), str):
                db.set_meta("overall_notes", body["notes"])
            if body.get("wave"):
                wave = str(body["wave"]).strip().lower()
                if wave not in DEFAULT_CITIES:
                    return self.json_out(400, {"error": "unknown_wave"})
                db.set_meta("active_wave", wave)
            return self.json_out(200, {"ok": True})

        if u.path == "/api/claim/checkout":
            if not self._board_ok(u):
                return self.json_out(403, {"error": "locked"})
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self.json_out(400, {"error": "bad json"})
            return self.start_claim(body)

        if u.path == "/webhook/stripe":
            return self.stripe_webhook(raw)

        if u.path == "/api/pipeline":
            if not self._board_ok(u):
                return self.json_out(403, {"error": "locked"})
            return self.run_pipeline()

        if u.path == "/pipeline/run":
            if not PIPELINE_TOKEN or self.headers.get("X-Pipeline-Token") != PIPELINE_TOKEN:
                return self.json_out(403, {"error": "bad or missing X-Pipeline-Token"})
            return self.run_pipeline()

        return self.send(404, page("Not found", "<h1>Not found</h1>"))

    def resend_webhook(self, raw: bytes):
        try:
            ev = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self.json_out(400, {"error": "bad json"})

        etype = ev.get("type", "")
        data = ev.get("data", {}) or {}
        to = (data.get("to") or [None])[0] if isinstance(data.get("to"), list) else data.get("to")
        print(f"  resend event: {etype} -> {to}")

        if etype in ("email.bounced", "email.complained") and to:
            # A complaint is an opt-out. Treat it as one immediately.
            db.suppress(to, etype)
        elif etype == "email.replied" and to:
            with db.conn() as c:
                c.execute("UPDATE leads SET replied = 1, status = 'replied' "
                          "WHERE lower(email) = ?", (to.lower(),))
        return self.json_out(200, {"ok": True})

    def _repo_path(self, name: str) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)

    def _send_repo_html(self, name: str, label: str, robots=True):
        try:
            with open(self._repo_path(name), "rb") as f:
                return self.send(200, f.read(), robots=robots)
        except OSError:
            return self.send(500, page(label, f"<h1>{name} missing</h1>"))

    def _board_ok(self, u) -> bool:
        if not BOARD_KEY:
            return False
        key = (parse_qs(u.query).get("k") or [""])[0]
        if key == BOARD_KEY:
            return True
        hdr = (self.headers.get("X-Pipeline-Token") or "").strip()
        return hdr == BOARD_KEY or (bool(PIPELINE_TOKEN) and hdr == PIPELINE_TOKEN)

    def claim_get(self, parts, u):
        q = parse_qs(u.query)
        action = parts[1] if len(parts) > 1 else ""
        if action == "start":
            token = (q.get("t") or [""])[0]
            care = claim.normalize_care((q.get("care") or ["none"])[0])
            lead = db.get_lead_by_token(token) if token else None
            if not lead:
                return self.send(404, page("Claim", "<h1>Lead not found</h1><p>Need a valid demo token.</p>"))
            result = claim.create_checkout(dict(lead), care)
            if result.get("session_id"):
                db.record_claim_pending(
                    lead["id"], care, result["session_id"], result.get("amount_cents") or 0)
            url = result.get("url") or claim.stub_checkout_url(token, care)
            self.send_response(302)
            self.send_header("Location", url)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if action == "stub":
            token = (q.get("t") or [""])[0]
            care = claim.normalize_care((q.get("care") or ["none"])[0])
            lead = db.get_lead_by_token(token) if token else None
            return self.send(200, claim.render_stub(dict(lead) if lead else None, care), robots=False)
        if action == "success":
            return self.send(200, claim.render_success((q.get("session_id") or [""])[0]), robots=False)
        if action == "cancel":
            return self.send(200, claim.render_cancel((q.get("t") or [""])[0]), robots=False)
        return self.send(404, page("Not found", "<h1>Not found</h1>"))

    def start_claim(self, body: dict):
        lead_id = int(body.get("lead_id") or body.get("id") or 0)
        care = claim.normalize_care(body.get("care"))
        lead = db.get_lead(lead_id) if lead_id else None
        if not lead and body.get("t"):
            lead = db.get_lead_by_token(str(body.get("t")))
        if not lead:
            return self.json_out(404, {"error": "lead_not_found", "pricing": claim.pricing()})
        result = claim.create_checkout(dict(lead), care)
        if result.get("session_id"):
            db.record_claim_pending(
                lead["id"], care, result["session_id"], result.get("amount_cents") or 0)
        return self.json_out(200 if result.get("ok") else 502, result)

    def stripe_webhook(self, raw: bytes):
        sig = self.headers.get("Stripe-Signature") or ""
        if not claim.STRIPE_WEBHOOK_SECRET:
            return self.json_out(200, {
                "ok": True, "stub": True,
                "message": "STRIPE_WEBHOOK_SECRET unset — webhook accepted but not applied.",
            })
        if not claim.verify_webhook(raw, sig):
            return self.json_out(400, {"error": "bad_signature"})
        try:
            ev = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self.json_out(400, {"error": "bad json"})
        etype = ev.get("type") or ""
        session = (ev.get("data") or {}).get("object") or {}
        if etype == "checkout.session.completed":
            meta = session.get("metadata") or {}
            lead_id = int(meta.get("lead_id") or 0)
            if not lead_id and session.get("client_reference_id"):
                try:
                    lead_id = int(session["client_reference_id"])
                except (TypeError, ValueError):
                    lead_id = 0
            care = claim.normalize_care(meta.get("care_plan"))
            amount = int(session.get("amount_total") or claim.amount_cents(care))
            if lead_id:
                db.mark_claimed(
                    lead_id, care_plan=care,
                    session_id=session.get("id") or "",
                    amount_cents=amount, status="paid")
            return self.json_out(200, {"ok": True, "applied": bool(lead_id)})
        return self.json_out(200, {"ok": True, "ignored": etype})

    def run_pipeline(self):
        """The full daily loop: scan -> build demo sites -> find emails -> send
        proposals, capped at DAILY_SEND_LIMIT sends. Each stage is independent
        so a slow/failed scan still lets today's backlog get emailed."""
        from datetime import timedelta
        from emailer import send_proposal, send_sms, build_sms
        from generator import generate_site
        from scanner.email_finder import find_email
        from scanner.scanner import daily_scan_sample, check_website

        found = daily_scan_sample(budget=12)

        made = []
        for lead in db.leads_needing_site(limit=DAILY_SEND_LIMIT):
            html_str, token = generate_site(
                name=lead["name"], address=lead["address"] or "", phone=lead["phone"] or "",
                category=lead["category"] or "restaurant", rating=lead["rating"],
                city=lead["city"] or "", lead_id=lead["id"], business_id=lead["business_id"],
                fetch_place=True)
            db.create_demo_site(lead["id"], lead["business_id"], html_str, token,
                                template_used=lead["category"])
            db.update_lead(lead["id"], status="site_generated", demo_token=token,
                           demo_created_at=datetime.now().isoformat(),
                           demo_expires_at=(datetime.now() +
                                            timedelta(hours=DEMO_EXPIRE_HOURS)).isoformat())
            made.append({"lead": lead["id"], "name": lead["name"], "token": token})

        enriched = []
        for lead in db.leads_missing_email(limit=DAILY_SEND_LIMIT * 2):
            email = find_email(lead["name"], lead["biz_website"], lead["website_status"])
            if email:
                db.set_email(lead["id"], lead["business_id"], email)
                enriched.append({"lead": lead["id"], "email": email})

        sent = []
        skipped_unknown = []
        for lead in db.leads_needing_email(limit=DAILY_SEND_LIMIT):
            if len(sent) >= DAILY_SEND_LIMIT:
                break
            if db.is_suppressed(lead["email"]):
                continue
            # Truthfulness gate: only pitch a business we have CONFIRMED has no
            # real website. "unknown" means the check could not answer, and the
            # lead waits rather than getting a false "you have no website" email.
            status, real_site = check_website(lead["name"], lead["address"] or "")
            if status == "has_site":
                db.update_lead(lead["id"], website_status="has_site", status="dead")
                continue
            if status == "unknown":
                db.update_lead(lead["id"], website_status="unknown")
                skipped_unknown.append({"lead": lead["id"], "name": lead["name"]})
                continue
            db.update_lead(lead["id"], website_status=status)
            url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"
            if lead["email"]:
                result = send_proposal(
                    business_name=str(lead["name"]), demo_url=url, owner_email=lead["email"],
                    category=lead["category"] or "business", city=lead["city"] or "",
                    lead_id=lead["id"])
                if result:
                    db.update_lead(lead["id"], emailed=1, email_sent_at=datetime.now().isoformat(),
                                   status="proposed")
                    sent.append({"lead": lead["id"], "email": lead["email"]})
            elif lead["phone"]:
                # No email — send SMS with demo link instead.
                body = build_sms(str(lead["name"]), url)
                if send_sms(lead["phone"], body):
                    db.update_lead(lead["id"], emailed=1, email_sent_at=datetime.now().isoformat(),
                                   status="proposed")
                    sent.append({"lead": lead["id"], "phone": lead["phone"]})

        return self.json_out(200, {
            "scanned_new": found, "sites_generated": len(made),
            "emails_found": len(enriched), "proposals_sent": len(sent),
            "skipped_unverified": len(skipped_unknown),
            "sites": made, "sent": sent, "unverified": skipped_unknown,
        })


def main():
    db.init_db()
    print(f"demo server on http://localhost:{PORT}")
    print(f"  /  /stats  /health  /demo/<token>  /ops  /claim/start  /unsubscribe  /webhook/resend  /pipeline/run")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
