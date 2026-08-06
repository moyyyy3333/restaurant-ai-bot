"""
Demo server.

  /                     health + counts
  /demo/<token>         serve a generated sample site (expires)
  /unsubscribe?e=...    one-click opt-out (GET renders, POST confirms)
  /webhook/resend       inbound reply/bounce events -> lead status
  /pipeline/run         token-guarded: full daily scan -> site -> email -> send

Stdlib only — no Flask needed, so `python server.py` just works.
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import db
from config import DAILY_SEND_LIMIT, DEMO_BASE_URL, DEMO_EXPIRE_HOURS, PORT

PIPELINE_TOKEN = os.getenv("PIPELINE_TOKEN", "")


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
    def send(self, code: int, body: bytes, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        self.wfile.write(body)

    def json_out(self, code: int, obj: dict):
        self.send(code, json.dumps(obj, default=str).encode(), "application/json")

    # ---------------------------------------------------------------------- GET
    def do_GET(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]

        if not parts:
            s = db.get_stats()
            return self.json_out(200, {"ok": True, "service": "local-business-ai-bot", **s})

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

    def serve_demo(self, token: str):
        lead = db.get_lead_by_token(token)
        demo = db.get_demo(token)
        if not demo or not lead:
            return self.send(404, page("Expired", "<h1>This sample isn't available</h1>"
                                       "<p>The link may have expired.</p>"))
        # expiry check
        exp = lead["demo_expires_at"]
        if exp:
            try:
                if datetime.fromisoformat(exp) < datetime.now():
                    return self.send(410, page("Expired", f"""
                        <h1>This sample has expired</h1>
                        <p>Samples stay up for {DEMO_EXPIRE_HOURS} hours. Reply to the email
                        that brought you here and it can be restored.</p>"""))
            except ValueError:
                pass
        path = demo["html_path"]
        if not path or not os.path.exists(path):
            return self.send(404, page("Missing", "<h1>Sample not found on disk</h1>"))
        db.bump_demo_views(token)
        with open(path, "rb") as f:
            return self.send(200, f.read())

    # --------------------------------------------------------------------- POST
    def do_POST(self):
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

    def run_pipeline(self):
        """The full daily loop: scan -> build demo sites -> find emails -> send
        proposals, capped at DAILY_SEND_LIMIT sends. Each stage is independent
        so a slow/failed scan still lets today's backlog get emailed."""
        from datetime import timedelta
        from emailer import send_proposal
        from generator import generate_site
        from scanner.email_finder import find_email
        from scanner.scanner import daily_scan_sample, verify_website

        found = daily_scan_sample(budget=12)

        made = []
        for lead in db.leads_needing_site(limit=DAILY_SEND_LIMIT):
            html_str, token = generate_site(
                name=lead["name"], address=lead["address"] or "", phone=lead["phone"] or "",
                category=lead["category"] or "restaurant", rating=lead["rating"],
                city=lead["city"] or "", lead_id=lead["id"], business_id=lead["business_id"])
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
        for lead in db.leads_needing_email(limit=DAILY_SEND_LIMIT):
            if len(sent) >= DAILY_SEND_LIMIT:
                break
            if db.is_suppressed(lead["email"]):
                continue
            if lead["website_status"] != "has_site":
                real_site = verify_website(lead["name"], lead["address"] or "")
                if real_site:
                    db.update_lead(lead["id"], website_status="has_site", status="dead")
                    continue
            url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"
            result = send_proposal(
                business_name=str(lead["name"]), demo_url=url, owner_email=lead["email"],
                category=lead["category"] or "business", city=lead["city"] or "",
                lead_id=lead["id"])
            if result:
                db.update_lead(lead["id"], emailed=1, email_sent_at=datetime.now().isoformat(),
                               status="proposed")
                sent.append({"lead": lead["id"], "email": lead["email"]})

        return self.json_out(200, {
            "scanned_new": found, "sites_generated": len(made),
            "emails_found": len(enriched), "proposals_sent": len(sent),
            "sites": made, "sent": sent,
        })


def main():
    db.init_db()
    print(f"demo server on http://localhost:{PORT}")
    print(f"  /demo/<token>  /unsubscribe  /webhook/resend  /pipeline/run")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
