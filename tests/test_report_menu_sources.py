"""Parser/classifier for scripts/report_menu_sources.py."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from report_menu_sources import (  # noqa: E402
    classify_source,
    parse_demo_html,
    render_markdown,
)


REAL_HTML = """<!DOCTYPE html><html><head>
<title>Thien An Sandwiches · Houston</title></head>
<body data-category="restaurant">
<section id="menu" data-menu-source="menu_page">
<article><h3>Banh Mi Ga</h3></article>
<article><h3>Cha Gio</h3></article>
<p class="sub menu-source">From their menu — not sample prices.</p>
</section></body></html>"""

SAMPLE_HTML = """<!DOCTYPE html><html><head>
<title>Yale Street Grill · Houston</title></head>
<body data-category="restaurant">
<section id="menu" data-menu-source="sample">
<article><h3>Breakfast plate</h3></article>
<article><h3>Pancakes</h3></article>
<p class="sub">Sample prices — your real menu replaces these.</p>
</section></body></html>"""


class ReportMenuSourcesTest(unittest.TestCase):
    def test_classify_source_real_and_sample(self):
        self.assertEqual(classify_source("menu_page"), "REAL")
        self.assertEqual(classify_source("order_page"), "REAL")
        self.assertEqual(classify_source("social_photo"), "REAL")
        self.assertEqual(classify_source("yelp"), "REAL")
        self.assertEqual(classify_source("sample"), "SAMPLE")
        self.assertEqual(classify_source(""), "UNKNOWN")
        self.assertEqual(classify_source(None), "UNKNOWN")

    def test_parse_real_menu(self):
        got = parse_demo_html(REAL_HTML)
        self.assertEqual(got["name"], "Thien An Sandwiches")
        self.assertEqual(got["city"], "Houston")
        self.assertEqual(got["category"], "restaurant")
        self.assertEqual(got["data_menu_source"], "menu_page")
        self.assertEqual(got["menu_class"], "REAL")
        self.assertIn("Banh Mi Ga", got["sniff"])

    def test_parse_sample_menu(self):
        got = parse_demo_html(SAMPLE_HTML)
        self.assertEqual(got["name"], "Yale Street Grill")
        self.assertEqual(got["data_menu_source"], "sample")
        self.assertEqual(got["menu_class"], "SAMPLE")
        self.assertIn("Breakfast plate", got["sniff"])
        self.assertIn("Sample prices", got["caption"])

    def test_parse_missing_source_is_unknown(self):
        got = parse_demo_html("<html><title>Mystery · Austin</title></html>", "Mystery")
        self.assertEqual(got["menu_class"], "UNKNOWN")
        self.assertEqual(got["city"], "Austin")

    def test_render_markdown_totals(self):
        rows = [
            {"name": "A", "city": "Houston", "category": "restaurant",
             "demo_url": "https://example.test/demo/a", "menu_class": "REAL",
             "notes": "data-menu-source=menu_page"},
            {"name": "B", "city": "Miami", "category": "cafe",
             "demo_url": "https://example.test/demo/b", "menu_class": "SAMPLE",
             "notes": "data-menu-source=sample"},
            {"name": "C", "city": "", "category": "",
             "demo_url": "https://example.test/demo/c", "menu_class": "UNKNOWN",
             "notes": "demo missing (404)"},
        ]
        md = render_markdown(rows, {"sites": 420, "funnel": {"demos": 401}}, "test", "now")
        self.assertIn("**1 real**", md)
        self.assertIn("**1 sample**", md)
        self.assertIn("**1 unknown/missing**", md)
        self.assertIn("https://example.test/demo/a", md)


if __name__ == "__main__":
    unittest.main()
