import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_render_is_the_only_runtime(self):
        self.assertFalse((ROOT / "vercel.json").exists())
        self.assertFalse((ROOT / ".vercel").exists())
        self.assertEqual(
            (ROOT / "Procfile").read_text().strip(),
            "web: python3 run.py",
        )

    def test_deploy_retries_render_api_and_checks_health(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        self.assertIn("--retry-all-errors", workflow)
        self.assertIn("group: render-production", workflow)
        self.assertIn("Render did not return a deploy id", workflow)
        self.assertIn("/health", workflow)
        self.assertIn("python3 run.py", (ROOT / "Procfile").read_text())


if __name__ == "__main__":
    unittest.main()
