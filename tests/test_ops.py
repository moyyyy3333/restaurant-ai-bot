"""Ops dashboard + Stripe claim stub using an isolated database."""
import hashlib
import hmac
import json
import tempfile
import time
import unittest
import urllib.parse
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from http.server import ThreadingHTTPServer

import db
import claim
import ops
import server


TOKEN = "ops-secret"
_TMP = Path(tempfile.mkdtemp()) / "ops-test.db"


class OpsAndClaimTests(unittest.TestCase):
    def setUp(self):
        db.TURSO_DATABASE_URL = str(_TMP)
        db.TURSO_AUTH_TOKEN = "test-token"
        db._schema_ready = False
        if _TMP.exists():
            _TMP.unlink()
        self._key = patch.object(server, "BOARD_KEY", TOKEN)
        self._tok = patch.object(server, "PIPELINE_TOKEN", TOKEN)
        self._key.start()
        self._tok.start()

    def tearDown(self):
        self._key.stop()
        self._tok.stop()

    def _serve(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd

    def _get(self, httpd, path):
        conn = HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, body, headers

    def _post(self, httpd, path, body=None, headers=None):
        conn = HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
        raw = json.dumps(body or {}).encode()
        hdrs = {"Content-Type": "application/json", "Content-Length": str(len(raw))}
        if headers:
            hdrs.update(headers)
        conn.request("POST", path, body=raw, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def _signed_stripe_post(self, httpd, event, secret="whsec_test"):
        raw = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        digest = hmac.new(
            secret.encode(), timestamp.encode() + b"." + raw,
            hashlib.sha256).hexdigest()
        return self._post(
            httpd, "/webhook/stripe", event,
            {"Stripe-Signature": f"t={timestamp},v1={digest}"})

    def _seed(self):
        db.ensure_schema()
        bid = db.upsert_business(
            google_place_id="ops-place-1", name="Montrose Plumbing",
            address="100 Westheimer", city="houston", category="plumber",
            phone="7135550100", rating=4.8, review_count=42,
            website_status="none")
        lid = db.create_lead(
            bid, name="Montrose Plumbing", address="100 Westheimer",
            city="houston", category="plumber", phone="7135550100",
            rating=4.8, website_status="none")
        db.update_lead(lid, demo_token="opsdemo1", status="proposed", emailed=1,
                       email="owner@plumb.test")
        bid2 = db.upsert_business(
            google_place_id="ops-place-2", name="Miami Cafe",
            city="miami", category="cafe", website_status="social_only")
        db.create_lead(bid2, name="Miami Cafe", city="miami", category="cafe",
                       website_status="social_only")
        return lid

    def test_ops_locked_without_token(self):
        httpd = self._serve()
        try:
            status, body, _ = self._get(httpd, "/ops")
            self.assertEqual(status, 403)
            self.assertIn(b"Locked", body)
            status, body, _ = self._get(httpd, "/api/ops")
            self.assertEqual(status, 403)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_ops_page_and_payload(self):
        self._seed()
        httpd = self._serve()
        try:
            status, body, headers = self._get(httpd, f"/ops?k={TOKEN}")
            self.assertEqual(status, 200)
            self.assertIn("text/html", headers.get("content-type", ""))
            self.assertIn(b"Prospect Board", body)
            self.assertIn(b"Today's focus", body)
            self.assertIn(b"Daily rhythm", body)
            self.assertIn(b"Weekly rotation", body)
            self.assertIn(b"Territory waves", body)
            self.assertIn(b"Houston", body)
            self.assertIn(b"Miami", body)
            self.assertIn(b"Austin", body)
            self.assertIn(b"Restaurant", body)
            self.assertIn(b"Cafe", body)
            self.assertIn(b"Trades", body)
            self.assertIn(b"Salon", body)
            self.assertIn(b"Auto", body)
            self.assertIn(b"Other", body)
            self.assertIn(b"not restaurant-only", body)
            self.assertIn(b"$99 builds it. Care keeps it live.", body)
            self.assertIn(b"Reload", body)
            self.assertIn(b"Pop out", body)
            self.assertIn(b"Quick note", body)
            self.assertIn(b"Copy for Claude/CoS", body)
            self.assertIn(b'data-tag="PIPELINE:"', body)
            self.assertIn(b'data-tag="RESEARCH:"', body)
            self.assertIn(b'data-tag="IDEA:"', body)
            self.assertIn(b"Auto-prep ON", body)
            self.assertIn(b"9 AM CT", body)
            self.assertIn(b"Re-run today's prep", body)
            self.assertIn(b"Refresh from database", body)
            self.assertIn(b"Claim", body)
            self.assertIn(b"$99", body)
            self.assertIn(b"$29", body)
            self.assertIn(b"$249", body)
            self.assertNotIn(b"$79", body)

            status, body, _ = self._get(httpd, f"/api/ops?k={TOKEN}")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertGreaterEqual(data["stats"]["leads"], 2)
            self.assertGreaterEqual(data["stats"]["emailed"], 1)
            self.assertIn("funnel", data["stats"])
            self.assertIn("by_website_status", data["stats"])
            self.assertEqual(data["stats"]["by_website_status"].get("none"), 1)
            self.assertEqual(data["stats"]["by_website_status"].get("social_only"), 1)
            self.assertEqual(len(data["waves"]), 3)
            self.assertEqual({w["city"] for w in data["waves"]}, {"houston", "miami", "austin"})
            self.assertEqual(len(data["rotation"]), 6)
            names = [l["name"] for l in data["leads"]]
            self.assertIn("Montrose Plumbing", names)
            self.assertEqual(data["claim"]["pricing"]["build"]["amount_usd"], 99)
            self.assertEqual(data["claim"]["pricing"]["care_monthly"]["amount_usd"], 29)
            self.assertTrue(data["claim"]["stub"])
            self.assertTrue(data["prep"]["auto"])
            self.assertEqual(data["prep"]["schedule"], "9 AM CT")
            self.assertIn("cta", data["today"])
            self.assertIn("none-site locals", data["today"]["blurb"])
            self.assertIn("Order for food", data["today"]["blurb"])
            labels = {d["label"] for d in data["rotation"]}
            self.assertEqual(
                labels, {"Restaurant", "Cafe", "Trades", "Salon", "Auto", "Other"})
            plumber = next(l for l in data["leads"] if l["name"] == "Montrose Plumbing")
            cafe = next(l for l in data["leads"] if l["name"] == "Miami Cafe")
            self.assertEqual(plumber["cta"], "Quote")
            self.assertEqual(cafe["cta"], "Order")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_ops_meta_wave_and_notes(self):
        httpd = self._serve()
        try:
            status, body = self._post(
                httpd, f"/api/ops/meta?k={TOKEN}",
                {"wave": "austin", "notes": "Focus Midtown next week",
                 "quick_note": "PIPELINE: text Houston plumbers", "prep": True})
            self.assertEqual(status, 200)
            status, body, _ = self._get(httpd, f"/api/ops?k={TOKEN}")
            data = json.loads(body)
            self.assertEqual(data["today"]["city"], "austin")
            self.assertEqual(data["notes"], "Focus Midtown next week")
            self.assertEqual(data["quick_note"], "PIPELINE: text Houston plumbers")
            self.assertTrue(data["prep"]["last_at"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_cta_hint_food_vs_trade(self):
        self.assertEqual(ops._cta_hint("restaurant"), "Order")
        self.assertEqual(ops._cta_hint("cafe"), "Order")
        self.assertEqual(ops._cta_hint("plumber"), "Quote")
        self.assertEqual(ops._cta_hint("auto"), "Quote")
        self.assertEqual(ops._cta_hint("salon"), "Book")
        self.assertEqual(ops._cta_hint("lawyer"), "Call")

    def test_claim_stub_without_stripe_keys(self):
        lid = self._seed()
        httpd = self._serve()
        try:
            status, body = self._post(
                httpd, f"/api/claim/checkout?k={TOKEN}",
                {"lead_id": lid, "care": "monthly"})
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["stub"])
            self.assertTrue(data["ok"])
            self.assertEqual(data["pricing"]["build"]["amount_usd"], 99)
            self.assertEqual(data["care_plan"], "monthly")
            self.assertIn("/claim/stub", data["url"])
            self.assertNotIn("79", json.dumps(data))

            status, body, _ = self._get(httpd, "/claim/start?t=opsdemo1&care=yearly")
            self.assertIn(status, (302, 301))

            status, body, _ = self._get(httpd, "/claim/stub?t=opsdemo1&care=yearly")
            self.assertEqual(status, 200)
            self.assertIn(b"$99", body)
            self.assertIn(b"$249", body)
            self.assertIn(b"Montrose Plumbing", body)
            self.assertNotIn(b"$79", body)

            status, body, _ = self._get(httpd, "/claim/success")
            self.assertEqual(status, 200)
            self.assertIn(b"$99", body)
            status, body, _ = self._get(httpd, "/claim/cancel")
            self.assertEqual(status, 200)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_demo_contains_buyer_claim_bar(self):
        self._seed()
        db.create_demo_site(
            1, 1, "<html><body>preview</body></html>", "opsdemo1")
        httpd = self._serve()
        try:
            status, body, _ = self._get(httpd, "/demo/opsdemo1")
            self.assertEqual(status, 200)
            self.assertIn(b"This is a preview built for Montrose Plumbing", body)
            self.assertIn(b"/claim/start?t=opsdemo1&amp;care=none", body)
            self.assertIn(b"Claim with Care", body)
            self.assertIn(b"What you get", body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_stripe_webhook_stub_without_secret(self):
        httpd = self._serve()
        try:
            status, body = self._post(httpd, "/webhook/stripe", {"type": "checkout.session.completed"})
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["stub"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_mark_claimed_updates_funnel(self):
        lid = self._seed()
        db.mark_claimed(lid, care_plan="monthly", session_id="", amount_cents=12800, status="stub")
        stats = db.get_stats()
        self.assertGreaterEqual(stats["claimed"], 1)
        self.assertGreaterEqual(stats["care"], 1)
        self.assertGreaterEqual(stats["funnel"]["claimed"], 1)

    def test_checkout_collects_phone_and_carries_subscription_metadata(self):
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"id":"cs_live","url":"https://checkout.stripe.test"}'

        def open_request(request, timeout=0):
            captured.update(urllib.parse.parse_qs(request.data.decode()))
            return Response()

        lead = {"id": 44, "demo_token": "demo-44", "name": "Cafe 44"}
        with patch("claim.urllib.request.urlopen", side_effect=open_request):
            result = claim._create_stripe_session(
                lead, "monthly", "https://success.test", "https://cancel.test")
        self.assertEqual(result["id"], "cs_live")
        self.assertEqual(captured["phone_number_collection[enabled]"], ["true"])
        self.assertEqual(captured["metadata[lead_id]"], ["44"])
        self.assertEqual(
            captured["subscription_data[metadata][care_plan]"], ["monthly"])

    def test_configured_stripe_failure_never_falls_back_to_stub(self):
        lead = {"id": 44, "demo_token": "demo-44", "name": "Cafe 44"}
        with patch.object(claim, "STRIPE_SECRET_KEY", "sk_live_test"), \
             patch.object(
                 claim, "_create_stripe_session",
                 return_value={"error": {"message": "provider unavailable"}}):
            result = claim.create_checkout(lead, "none")
        self.assertFalse(result["ok"])
        self.assertFalse(result["stub"])
        self.assertIsNone(result["url"])

    def test_signed_checkout_webhook_is_idempotent(self):
        lead_id = self._seed()
        event = {
            "id": "evt_checkout_paid_1",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_paid_1",
                "amount_total": 12800,
                "customer": "cus_1",
                "subscription": "sub_1",
                "metadata": {
                    "lead_id": str(lead_id),
                    "care_plan": "monthly",
                    "demo_token": "opsdemo1",
                },
                "customer_details": {
                    "email": "buyer@example.test",
                    "phone": "+17135550101",
                },
            }},
        }
        httpd = self._serve()
        try:
            with patch.object(claim, "STRIPE_WEBHOOK_SECRET", "whsec_test"), \
                 patch("notifications.notify_admin", return_value=True) as notify, \
                 patch("emailer.send_welcome_email", return_value="email_1") as welcome:
                first_status, first_body = self._signed_stripe_post(httpd, event)
                second_status, second_body = self._signed_stripe_post(httpd, event)
            self.assertEqual(first_status, 200)
            self.assertTrue(json.loads(first_body)["applied"])
            self.assertEqual(second_status, 200)
            self.assertTrue(json.loads(second_body)["duplicate"])
            notify.assert_called_once()
            welcome.assert_called_once()
            lead = db.get_lead(lead_id)
            self.assertEqual(lead["status"], "claimed")
            self.assertEqual(lead["care_status"], "active")
            self.assertIsNone(lead["demo_expires_at"])
            with db.conn() as connection:
                claims = connection.execute(
                    "SELECT COUNT(*) FROM claims WHERE stripe_session_id='cs_paid_1'"
                ).fetchone()[0]
                events = connection.execute(
                    "SELECT COUNT(*) FROM stripe_events "
                    "WHERE event_id='evt_checkout_paid_1'"
                ).fetchone()[0]
            self.assertEqual(claims, 1)
            self.assertEqual(events, 1)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_stripe_lifecycle_events_update_claim_and_care(self):
        lead_id = self._seed()
        db.record_claim_pending(lead_id, "monthly", "cs_expired", 12800)
        db.mark_claimed(
            lead_id, "monthly", "cs_paid", 12800,
            subscription_id="sub_lifecycle", customer_id="cus_lifecycle")
        events = [
            {
                "id": "evt_expired",
                "type": "checkout.session.expired",
                "data": {"object": {"id": "cs_expired"}},
            },
            {
                "id": "evt_invoice",
                "type": "invoice.paid",
                "data": {"object": {
                    "subscription": "sub_lifecycle",
                    "customer": "cus_lifecycle",
                }},
            },
            {
                "id": "evt_cancel",
                "type": "customer.subscription.deleted",
                "data": {"object": {
                    "id": "sub_lifecycle",
                    "customer": "cus_lifecycle",
                    "metadata": {"lead_id": str(lead_id)},
                }},
            },
        ]
        httpd = self._serve()
        try:
            with patch.object(claim, "STRIPE_WEBHOOK_SECRET", "whsec_test"):
                for event in events:
                    status, body = self._signed_stripe_post(httpd, event)
                    self.assertEqual(status, 200, body)
            expired = db.get_claim_by_session("cs_expired")
            self.assertEqual(expired["status"], "expired")
            lead = db.get_lead(lead_id)
            self.assertEqual(lead["care_status"], "cancelled")
            self.assertIn("Care subscription cancelled", lead["notes"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_existing_public_routes_still_work(self):
        httpd = self._serve()
        try:
            status, body, _ = self._get(httpd, "/")
            self.assertEqual(status, 200)
            self.assertIn(b"<!DOCTYPE html>", body)
            status, body, _ = self._get(httpd, "/stats")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])
            self.assertIn("leads", data)
            status, body, _ = self._get(httpd, "/health")
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["ok"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_header_token_unlocks_api(self):
        httpd = self._serve()
        try:
            conn = HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
            conn.request("GET", "/api/ops", headers={"X-Pipeline-Token": TOKEN})
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            self.assertEqual(resp.status, 200)
            self.assertIn("funnel", json.loads(body)["stats"])
        finally:
            httpd.shutdown()
            httpd.server_close()
