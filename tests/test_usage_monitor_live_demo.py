from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_limit_patch.usage_monitor.live_demo import (
    build_live_payload,
    write_browser_payload,
)
from codex_limit_patch.usage_monitor.models import AccountSnapshot
from codex_limit_patch.usage_monitor.providers.base import (
    FetchAttempt,
    ProviderFetchOutcome,
)
from codex_limit_patch.usage_monitor.providers.codex import CODEX_DESCRIPTOR


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "demos" / "milestone-1" / "snapshots.json"
MILESTONE_ONE_DASHBOARD = ROOT / "demos" / "milestone-1" / "dashboard.js"
MILESTONE_TWO_DIR = ROOT / "demos" / "milestone-2"
NOW = datetime(2026, 7, 11, 4, 0, 0, tzinfo=timezone.utc)


def codex_outcome() -> ProviderFetchOutcome:
    snapshot = AccountSnapshot.from_dict(
        {
            "id": "openai-codex",
            "provider_id": "openai",
            "provider_name": "OpenAI",
            "client_name": "Codex",
            "account_kind": "subscription",
            "status": "available",
            "source_type": "local_client",
            "source_label": "Codex app-server",
            "fetched_at": "2026-07-11T04:00:00Z",
            "stale_after_seconds": 300,
            "plan_name": "plus",
            "quotas": [
                {
                    "id": "five-hour",
                    "label": "5-hour window",
                    "unit": "percent",
                    "remaining": 64,
                    "remaining_percent": 64,
                }
            ],
            "models": [],
        }
    )
    attempt = FetchAttempt(
        strategy_id="openai.codex-app-server",
        source_type="local_client",
        source_label="Codex app-server",
        available=True,
        success=True,
    )
    return ProviderFetchOutcome(
        descriptor=CODEX_DESCRIPTOR,
        snapshot=snapshot,
        attempts=(attempt,),
    )


class UsageMonitorLiveDemoTests(unittest.TestCase):
    def test_live_demo_replaces_only_synthetic_openai_row(self) -> None:
        payload = build_live_payload(
            FIXTURE_PATH,
            codex_outcome=codex_outcome(),
            now=NOW,
        )

        openai = [
            item for item in payload["accounts"] if item["provider_id"] == "openai"
        ]
        self.assertEqual(len(openai), 1)
        self.assertEqual(openai[0]["source_label"], "Codex app-server")
        self.assertFalse(openai[0]["demo"])
        self.assertEqual(len(payload["accounts"]), 5)

    def test_live_demo_marks_every_other_provider_as_demo(self) -> None:
        payload = build_live_payload(
            FIXTURE_PATH,
            codex_outcome=codex_outcome(),
            now=NOW,
        )

        non_openai = [
            item for item in payload["accounts"] if item["provider_id"] != "openai"
        ]
        self.assertTrue(all(item["demo"] for item in non_openai))
        self.assertTrue(payload["mixed_sources"])
        self.assertEqual(payload["live_provider_ids"], ["openai"])

    def test_browser_payload_writer_uses_expected_assignment(self) -> None:
        payload = build_live_payload(
            FIXTURE_PATH,
            codex_outcome=codex_outcome(),
            now=NOW,
        )
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "demo-data.js"

            write_browser_payload(payload, output)

            text = output.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("window.USAGE_MONITOR_DEMO = "))
            decoded = json.loads(text[len("window.USAGE_MONITOR_DEMO = ") : -2])
            self.assertEqual(decoded["accounts"][0]["plan_name"], "plus")

    def test_dashboard_renders_plan_and_per_account_demo_state(self) -> None:
        script = MILESTONE_ONE_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("account.plan_name", script)
        self.assertIn("account.demo", script)

    def test_milestone_two_preserves_example_and_live_entrypoints(self) -> None:
        example = (MILESTONE_TWO_DIR / "index.html").read_text(encoding="utf-8")
        live = (MILESTONE_TWO_DIR / "index-live.html").read_text(encoding="utf-8")

        self.assertIn("demo-data.example.js", example)
        self.assertIn("demo-data.js", live)
        self.assertTrue((MILESTONE_TWO_DIR / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
