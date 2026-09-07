import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import db
import pipeline
import server
from scanner import scanner


_TMP = Path(tempfile.mkdtemp()) / "pipeline-test.db"


class PipelineDryRunTests(unittest.TestCase):
    def setUp(self):
        db.TURSO_DATABASE_URL = str(_TMP)
        db.TURSO_AUTH_TOKEN = "test-token"
        db._schema_ready = False
        if _TMP.exists():
            _TMP.unlink()
        db.init_db()

    def _seed_ready_lead(self, email="owner@example.test", phone=""):
        bid = db.upsert_business(
            google_place_id="pipeline-place", name="Truthful Cafe",
            address="100 Main", city="houston", category="cafe",
            website_status="none")
        lead_id = db.create_lead(
            bid, name="Truthful Cafe", email=email, phone=phone,
            address="100 Main", city="houston", category="cafe",
            website_status="none")
        db.update_lead(
            lead_id, demo_token="dry-token", status="site_generated")
        return lead_id

    def test_zero_send_limit_reports_without_sending(self):
        self._seed_ready_lead()
        with patch("scanner.scanner.check_website", return_value=("none", "")), \
             patch("emailer.send_proposal", side_effect=AssertionError("must not send")):
            report = pipeline.run_daily(send_limit=0, scan_budget=0)
        self.assertTrue(report["ok"])
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["would_send"], 1)
        self.assertEqual(report["proposals_sent"], 0)

    def test_phone_only_lead_is_a_pipeline_candidate(self):
        lead_id = self._seed_ready_lead(email="", phone="+17135550100")
        candidates = db.leads_needing_email()
        self.assertEqual([row["id"] for row in candidates], [lead_id])

    def test_daily_budget_stops_at_limit(self):
        self.assertTrue(db.consume_daily_budget("test_provider", 2))
        self.assertTrue(db.consume_daily_budget("test_provider", 2))
        self.assertFalse(db.consume_daily_budget("test_provider", 2))

    def test_protected_endpoint_header_forces_zero_send_limit(self):
        fake = SimpleNamespace(
            headers={
                "X-Pipeline-Dry-Run": "true",
                "X-Pipeline-Scan-Budget": "1",
                "X-Pipeline-Scan-Results": "1",
                "X-Pipeline-Work-Limit": "1",
            },
            json_out=lambda status, report: (status, report),
        )
        with patch("pipeline.run_daily", return_value={"ok": True}) as run:
            status, _report = server.Handler.run_pipeline(fake)
        self.assertEqual(status, 200)
        run.assert_called_once_with(
            send_limit=0, scan_budget=1, scan_max_results=1, work_limit=1)

    def test_discovery_probe_limits_results_per_area(self):
        with patch("scanner.scanner.scan_area", return_value=0) as scan, \
             patch("scanner.scanner.time.sleep"):
            scanner.daily_scan_sample(
                budget=1, cities=["houston"], categories=["restaurant"],
                max_results=1)
        self.assertEqual(scan.call_count, 1)
        self.assertEqual(scan.call_args.kwargs["max_results"], 1)


if __name__ == "__main__":
    unittest.main()
