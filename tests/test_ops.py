"""Ops dashboard + Stripe claim stub. Shares the isolated DB from test_server."""
import json
import unittest
from http.client import HTTPConnection
from threading import Thread
from unittest.mock import patch

from http.server import ThreadingHTTPServer

from tests.test_server import db, server, _TMP


TOKEN = "ops-secret"


class OpsAndClaimTests(unittest.TestCase):
    def setUp(self):
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
            self.assertIn(b"Ops Board", body)
            self.assertIn(b"Today's focus", body)
            self.assertIn(b"Daily rhythm", body)
            self.assertIn(b"Weekly rotation", body)
            self.assertIn(b"Territory waves", body)
            self.assertIn(b"Houston", body)
            self.assertIn(b"Miami", body)
            self.assertIn(b"Austin", body)
            self.assertIn(b"$99", body)
            self.assertIn(b"$29", body)
            self.assertIn(b"$249", body)
            self.assertNotIn(b"$79", body)
            self.assertNotIn(b"Copy for Claude", body)

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
            self.assertEqual(len(data["rotation"]), 5)
            names = [l["name"] for l in data["leads"]]
            self.assertIn("Montrose Plumbing", names)
            self.assertEqual(data["claim"]["pricing"]["build"]["amount_usd"], 99)
            self.assertEqual(data["claim"]["pricing"]["care_monthly"]["amount_usd"], 29)
            self.assertTrue(data["claim"]["stub"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_ops_meta_wave_and_notes(self):
        httpd = self._serve()
        try:
            status, body = self._post(
                httpd, f"/api/ops/meta?k={TOKEN}",
                {"wave": "austin", "notes": "Focus Midtown next week"})
            self.assertEqual(status, 200)
            status, body, _ = self._get(httpd, f"/api/ops?k={TOKEN}")
            data = json.loads(body)
            self.assertEqual(data["today"]["city"], "austin")
            self.assertEqual(data["notes"], "Focus Midtown next week")
        finally:
            httpd.shutdown()
            httpd.server_close()

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
