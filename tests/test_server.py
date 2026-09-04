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
_TMP = Path(tempfile.mkdtemp()) / "test.db"
os.environ["TURSO_DATABASE_URL"] = str(_TMP)
os.environ["TURSO_AUTH_TOKEN"] = "test-token"

import db  # noqa: E402
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
        conn.close()
        return resp.status, body

    def test_homepage_creates_schema_and_returns_ok(self):
        httpd = self._serve()
        try:
            status, body = self._get(httpd, "/")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])
            self.assertEqual(data["service"], "local-business-ai-bot")
            self.assertEqual(data["leads"], 0)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_health_always_200(self):
        httpd = self._serve()
        try:
            status, body = self._get(httpd, "/health")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])
            self.assertIn(data["db"], ("ok", "unconfigured", "error"))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_homepage_survives_stats_failure(self):
        httpd = self._serve()
        try:
            with patch.object(db, "get_stats", side_effect=ValueError("no such table: leads")):
                status, body = self._get(httpd, "/")
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
            status, body = self._get(httpd, f"/demo/{token}")
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
            status, body = self._get(httpd, "/unsubscribe?e=owner@example.com")
            self.assertEqual(status, 200)
            self.assertIn(b"Stop emails", body)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
