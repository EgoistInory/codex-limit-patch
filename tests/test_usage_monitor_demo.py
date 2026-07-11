from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_limit_patch.usage_monitor.alerts import evaluate_alerts
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


if __name__ == "__main__":
    unittest.main()
