"""Growth demo email draft — copy only. Does not send."""
import os
import tempfile
import unittest
from pathlib import Path

_TMP = Path(tempfile.mkdtemp()) / "emailer-test.db"
os.environ["TURSO_DATABASE_URL"] = str(_TMP)
os.environ["TURSO_AUTH_TOKEN"] = "test-token"

from emailer import _subject_for, build_email  # noqa: E402


class EmailDraftTests(unittest.TestCase):
    def test_subject_a_cafe_tweak(self):
        self.assertEqual(_subject_for("cafe"), "Your cafe deserves a real website")
        self.assertEqual(_subject_for("restaurant"), "Your restaurant deserves a real website")
        self.assertEqual(_subject_for("shop"), "Your shop deserves a real website")
        self.assertEqual(_subject_for("business"), "Your business deserves a real website")
        self.assertEqual(_subject_for("florist"), "Your business deserves a real website")
        self.assertEqual(
            build_email("Ace Plumbing", "https://example.test/d", "a@b.com", "plumber")[0],
            "Your shop deserves a real website")
        self.assertEqual(
            build_email("Bloom Co", "https://example.test/d", "a@b.com", "florist")[0],
            "Your business deserves a real website")

    def test_pain_care_split_and_prices(self):
        subject, html, text = build_email(
            "Morning Light Coffee", "https://example.test/demo/abc",
            "owner@example.com", "cafe", "houston")
        self.assertEqual(subject, "Your cafe deserves a real website")
        for blob in (html, text):
            self.assertIn("Having a site is a pain", blob)
            self.assertIn("takes that off your plate", blob)
            self.assertIn("$99", blob)
            self.assertIn("$29", blob)
            self.assertIn("$249", blob)
            self.assertNotIn("$79", blob)
            self.assertNotIn("$299", blob)
        self.assertIn("unsolicited", text.lower())
        self.assertIn("/unsubscribe", text)

    def test_build_does_not_send(self):
        subject, html, _ = build_email(
            "Via313", "https://example.test/demo/x", "a@b.com", "restaurant")
        self.assertTrue(subject.startswith("Your restaurant"))
        self.assertIn("unsubscribe", html.lower())


if __name__ == "__main__":
    unittest.main()
