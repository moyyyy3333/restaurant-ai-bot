"""Homepage / health must never crash the Vercel function."""
import json
import os
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import patch

# Point Turso at a throwaway file before importing app modules.
# landing/config must not be imported before this, or they freeze an empty URL
# and tests share /tmp/restaurant-ai-bot.db.
_TMP = Path(tempfile.mkdtemp()) / "test.db"
os.environ["TURSO_DATABASE_URL"] = str(_TMP)
os.environ["TURSO_AUTH_TOKEN"] = "test-token"

import db  # noqa: E402
import landing  # noqa: E402
import server  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402


class HandlerTests(unittest.TestCase):
    def setUp(self):
        db._schema_ready = False
        if _TMP.exists():
            _TMP.unlink()

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

    def test_homepage_creates_schema_and_returns_html(self):
        httpd = self._serve()
        try:
            status, body, headers = self._get(httpd, "/")
            self.assertEqual(status, 200)
            self.assertIn("text/html", headers.get("content-type", ""))
            self.assertNotIn("noindex", headers.get("x-robots-tag", ""))
            self.assertIn(b"<!DOCTYPE html>", body)
            self.assertIn("No website? We’ll build".encode(), body)
            self.assertIn(b'class="extra">you </span>one.', body)
            self.assertIn(b"Get ", body)
            self.assertIn(b"free ", body)
            self.assertIn(b"preview", body)
            self.assertIn(landing.SUB.encode(), body)
            self.assertIn(landing.ONE_LINER.encode(), body)
            self.assertIn(b"We find you", body)
            self.assertIn(b"We build a preview", body)
            self.assertIn(b"You approve", body)
            self.assertIn(b'id="how-it-works"', body)
            self.assertIn(landing.EMPTY_SITES.encode(), body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_homepage_uses_long_copy_when_layout_has_room(self):
        httpd = self._serve()
        try:
            _, body, _ = self._get(httpd, "/")
            self.assertIn(b'class="extra">you </span>', body)
            self.assertIn(b".extra { display: none; }", body)
            self.assertIn(b".extra { display: inline; }", body)
            self.assertIn(landing.PRICE_LINE.encode(), body)
            self.assertIn(landing.PRICE_ONE_LINER.encode(), body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_stats_returns_former_homepage_json(self):
        httpd = self._serve()
        try:
            status, body, headers = self._get(httpd, "/stats")
            self.assertEqual(status, 200)
            self.assertIn("application/json", headers.get("content-type", ""))
            data = json.loads(body)
            self.assertTrue(data["ok"])
            self.assertEqual(data["service"], "local-business-ai-bot")
            self.assertEqual(data["leads"], 0)
            self.assertEqual(data["sites"], 0)
            self.assertIn("businesses", data)
            self.assertIn("by_city", data)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_health_always_200(self):
        httpd = self._serve()
        try:
            for path in ("/health", "/api/health"):
                status, body, _ = self._get(httpd, path)
                self.assertEqual(status, 200)
                data = json.loads(body)
                self.assertTrue(data["ok"])
                self.assertIn(data["db"], ("ok", "unconfigured", "error"))
                self.assertNotIn("leads", data)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_homepage_survives_stats_failure(self):
        httpd = self._serve()
        try:
            with patch.object(db, "get_stats", side_effect=ValueError("no such table: leads")):
                status, body, _ = self._get(httpd, "/")
            self.assertEqual(status, 200)
            self.assertIn(b"<!DOCTYPE html>", body)
            self.assertIn("No website? We’ll build".encode(), body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_stats_survives_stats_failure(self):
        httpd = self._serve()
        try:
            with patch.object(db, "get_stats", side_effect=ValueError("no such table: leads")):
                status, body, _ = self._get(httpd, "/stats")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])
            self.assertEqual(data.get("error"), "stats_unavailable")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_get_stats_bootstraps_missing_leads_table(self):
        # Production crashed here: GET / -> get_stats -> no such table: leads
        stats = db.get_stats()
        self.assertEqual(stats["leads"], 0)
        self.assertEqual(stats["sites"], 0)

    def test_demo_regenerates_when_file_missing(self):
        db.ensure_schema()
        bid = db.upsert_business(
            google_place_id="test-place-1", name="Taqueria Test",
            address="123 Main St", city="houston", category="restaurant",
            phone="7135550100", rating=4.5)
        lid = db.create_lead(
            bid, name="Taqueria Test", address="123 Main St", city="houston",
            category="restaurant", phone="7135550100", rating=4.5)
        token = "testtoken1"
        db.update_lead(lid, demo_token=token, status="site_generated")
        with db.conn() as c:
            c.execute(
                """INSERT INTO demo_sites
                   (lead_id, business_id, token, html_path, created_at)
                   VALUES (?,?,?,?,?)""",
                (lid, bid, token, "/no/such/path.html", db.now()))
        httpd = self._serve()
        try:
            status, body, _ = self._get(httpd, f"/demo/{token}")
            self.assertEqual(status, 200)
            self.assertIn(b"Taqueria Test", body)
            self.assertIn(b"<!DOCTYPE html>", body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_empty_turso_url_uses_local_file(self):
        local = Path(tempfile.mkdtemp()) / "ephemeral.db"
        with patch.object(db, "TURSO_DATABASE_URL", ""), \
             patch.object(db, "_LOCAL_DB", str(local)):
            db._schema_ready = False
            db.ensure_schema()
            stats = db.get_stats()
            self.assertEqual(stats["leads"], 0)
            self.assertTrue(local.exists())

    def test_unsubscribe_get(self):
        httpd = self._serve()
        try:
            status, body, _ = self._get(httpd, "/unsubscribe?e=owner@example.com")
            self.assertEqual(status, 200)
            self.assertIn(b"Stop emails", body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_homepage_mailto_uses_reply_to(self):
        httpd = self._serve()
        try:
            with patch.object(landing, "REPLY_TO", "owner@example.com"), \
                 patch.object(landing, "FROM_EMAIL", "onboarding@resend.dev"):
                # preview_contact_email reads module-level names
                with patch.object(server, "preview_contact_email",
                                  lambda: "owner@example.com"):
                    _, body, _ = self._get(httpd, "/")
            self.assertIn(b"mailto:owner@example.com", body)
        finally:
            httpd.shutdown()
            httpd.server_close()


class ContactEmailTests(unittest.TestCase):
    def test_prefers_reply_to(self):
        with patch.object(landing, "REPLY_TO", "replies@studio.test"), \
             patch.object(landing, "FROM_EMAIL", "from@studio.test"):
            self.assertEqual(landing.preview_contact_email(), "replies@studio.test")

    def test_skips_resend_sandbox_from(self):
        with patch.object(landing, "REPLY_TO", ""), \
             patch.object(landing, "FROM_EMAIL", "onboarding@resend.dev"):
            self.assertEqual(landing.preview_contact_email(), "")

    def test_uses_real_from_when_no_reply_to(self):
        with patch.object(landing, "REPLY_TO", ""), \
             patch.object(landing, "FROM_EMAIL", "hello@studio.test"):
            self.assertEqual(landing.preview_contact_email(), "hello@studio.test")


if __name__ == "__main__":
    unittest.main()
