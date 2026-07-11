from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_limit_patch.usage_monitor.alerts import evaluate_alerts
from codex_limit_patch.usage_monitor.demo import generate_demo_data
from codex_limit_patch.usage_monitor.models import load_snapshots


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demos" / "milestone-1"
DEMO_PATH = DEMO_DIR / "snapshots.json"
NOW = datetime(2026, 7, 11, 3, 0, 0, tzinfo=timezone.utc)


class UsageMonitorDemoTests(unittest.TestCase):
    def test_demo_contains_five_representative_sources(self) -> None:
        raw = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        snapshots = load_snapshots(raw["accounts"])

        self.assertEqual(
            {item.provider_id for item in snapshots},
            {"openai", "anthropic", "deepseek", "zhipu", "xiaomi"},
        )
        self.assertTrue(any(evaluate_alerts(item, now=NOW) for item in snapshots))

    def test_demo_keeps_provider_specific_metric_shapes(self) -> None:
        raw = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        snapshots = {item.provider_id: item for item in load_snapshots(raw["accounts"])}

        self.assertIsNone(snapshots["deepseek"].quotas[0].remaining_percent)
        self.assertEqual(snapshots["zhipu"].quotas[0].accuracy, "estimated")
        self.assertIsNone(snapshots["xiaomi"].quotas[0].remaining)
        self.assertEqual(snapshots["xiaomi"].status, "unavailable")

    def test_demo_generator_writes_browser_payload(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "demo-data.js"

            result = generate_demo_data(DEMO_PATH, output, now=NOW)

            self.assertEqual(result, output)
            text = output.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("window.USAGE_MONITOR_DEMO = "))
            self.assertIn('"alerts"', text)
            prefix = "window.USAGE_MONITOR_DEMO = "
            payload = json.loads(text[len(prefix) : -2])
            self.assertEqual(payload["alerts"][0]["severity"], "critical")

    def test_dashboard_has_required_assets(self) -> None:
        html = (DEMO_DIR / "index.html").read_text(encoding="utf-8")

        self.assertIn("styles.css", html)
        self.assertIn("demo-data.js", html)
        self.assertIn("dashboard.js", html)


if __name__ == "__main__":
    unittest.main()
