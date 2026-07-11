from __future__ import annotations

import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.providers.codex import (
    CodexAppServerStrategy,
    fetch_codex_outcome,
)


NOW = datetime(2026, 7, 11, 4, 0, 0, tzinfo=timezone.utc)
RESPONSE = {
    "result": {
        "rateLimits": {
            "primary": {
                "usedPercent": 23,
                "windowDurationMins": 300,
                "resetsAt": "2026-07-11T05:20:00Z",
            },
            "secondary": {
                "usedPercent": 20,
                "windowDurationMins": 10080,
                "resetsAt": "2026-07-16T00:00:00Z",
            },
            "planType": "plus",
        },
        "rateLimitResetCredits": {"availableCount": 2},
    }
}


class FakeClient:
    def __init__(self, response) -> None:
        self.response = response

    def read_rate_limits(self):
        return self.response


class CodexUsageProviderTests(unittest.TestCase):
    def test_strategy_maps_windows_plan_and_reset_credits(self) -> None:
        snapshot = CodexAppServerStrategy(client=FakeClient(RESPONSE)).fetch(NOW)

        self.assertEqual(snapshot.plan_name, "plus")
        self.assertEqual([quota.id for quota in snapshot.quotas], [
            "five-hour",
            "weekly",
            "reset-credits",
        ])
        self.assertEqual(snapshot.quotas[0].remaining_percent, 77)
        self.assertEqual(snapshot.quotas[1].remaining_percent, 80)
        self.assertEqual(snapshot.quotas[2].remaining, 2)
        self.assertEqual(snapshot.quotas[0].resets_at, "2026-07-11T05:20:00Z")

    def test_fetch_outcome_uses_codex_app_server_source(self) -> None:
        outcome = fetch_codex_outcome(client=FakeClient(RESPONSE), now=NOW)

        self.assertEqual(outcome.snapshot.provider_id, "openai")
        self.assertEqual(outcome.snapshot.client_name, "Codex")
        self.assertEqual(outcome.snapshot.source_label, "Codex app-server")
        self.assertTrue(outcome.attempts[0].success)

    def test_rate_limit_reached_keeps_snapshot_available_with_zero_remaining(self) -> None:
        response = {
            "result": {
                "rateLimits": {
                    "primary": {"usedPercent": 100},
                    "rateLimitReachedType": "primary",
                }
            }
        }

        snapshot = CodexAppServerStrategy(client=FakeClient(response)).fetch(NOW)

        self.assertEqual(snapshot.status, "available")
        self.assertEqual(snapshot.quotas[0].remaining_percent, 0)
        self.assertIn("exhausted", snapshot.message)


if __name__ == "__main__":
    unittest.main()
