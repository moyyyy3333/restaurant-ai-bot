import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from export_demos_index import (  # noqa: E402
    CSV_COLS,
    PROD_HOST,
    demo_url,
    sort_rows,
    write_csv,
    write_md,
)


class ExportDemosIndexTests(unittest.TestCase):
    def test_public_url_pattern(self):
        self.assertEqual(
            demo_url("EBMKiuowROVS"),
            "https://restaurant-ai-bot-two.vercel.app/demo/EBMKiuowROVS",
        )
        self.assertTrue(PROD_HOST.endswith("restaurant-ai-bot-two.vercel.app"))

    def test_committed_index_is_real_tokens_only(self):
        rows = list(csv.DictReader((ROOT / "demos-index.csv").open(encoding="utf-8")))
        seed = json.loads((ROOT / "scripts" / "demo_index_seed.json").read_text(encoding="utf-8"))
        self.assertEqual([r["token"] for r in rows], [r["token"] for r in seed])
        tokens = [r["token"] for r in rows]
        self.assertTrue(tokens)
        self.assertEqual(len(tokens), len(set(tokens)))
        self.assertTrue(all(tokens))
        self.assertTrue(all(r["demo_url"] == demo_url(r["token"]) for r in rows))
        self.assertEqual(list(rows[0].keys()), CSV_COLS)
        md = (ROOT / "demos-index.md").read_text(encoding="utf-8")
        self.assertIn("| name | demo_url |", md)
        for row in rows:
            self.assertIn(row["demo_url"], md)

    def test_write_csv_and_md_round_trip(self):
        rows = sort_rows([
            {
                "name": "Beta Cafe",
                "demo_url": demo_url("bbb"),
                "city": "miami",
                "category": "cafe",
                "website_status": "none",
                "token": "bbb",
                "lead_id": "2",
            },
            {
                "name": "Alpha Grill",
                "demo_url": demo_url("aaa"),
                "city": "houston",
                "category": "restaurant",
                "website_status": "",
                "token": "aaa",
                "lead_id": "1",
            },
        ])
        self.assertEqual([r["name"] for r in rows], ["Alpha Grill", "Beta Cafe"])
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "demos-index.csv"
            md_path = Path(tmp) / "demos-index.md"
            write_csv(csv_path, rows)
            write_md(md_path, rows, "turso", 401)
            out = list(csv.DictReader(csv_path.open(encoding="utf-8")))
            self.assertEqual(out[0]["name"], "Alpha Grill")
            md = md_path.read_text(encoding="utf-8")
            self.assertIn("Rows in this file: **2**", md)
            self.assertIn("| Alpha Grill | https://restaurant-ai-bot-two.vercel.app/demo/aaa |", md)


if __name__ == "__main__":
    unittest.main()
