from __future__ import annotations

import unittest

from codex_limit_patch.usage_monitor.models import AccountSnapshot, load_snapshots


class UsageMonitorModelTests(unittest.TestCase):
    def test_snapshot_round_trip_preserves_unknown_quota(self) -> None:
        raw = {
            "id": "xiaomi-main",
            "provider_id": "xiaomi",
            "provider_name": "Xiaomi MiMo",
            "account_kind": "api",
            "status": "unavailable",
            "source_type": "official_api",
            "source_label": "Official API",
            "fetched_at": "2026-07-11T02:00:00Z",
            "stale_after_seconds": 900,
            "quotas": [
                {
                    "id": "balance",
                    "label": "API balance",
                    "unit": "CNY",
                }
            ],
            "models": [],
        }

        snapshot = AccountSnapshot.from_dict(raw)

        self.assertIsNone(snapshot.quotas[0].remaining)
        self.assertIsNone(snapshot.to_dict()["quotas"][0]["remaining"])

    def test_snapshot_rejects_missing_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider_id"):
            AccountSnapshot.from_dict({"id": "broken"})

    def test_load_snapshots_builds_models_and_metrics(self) -> None:
        raw = {
            "id": "deepseek-main",
            "provider_id": "deepseek",
            "provider_name": "DeepSeek",
            "account_kind": "api",
            "status": "available",
            "source_type": "official_api",
            "source_label": "Balance API",
            "fetched_at": "2026-07-11T02:00:00Z",
            "stale_after_seconds": 900,
            "requests_today": 42,
            "quotas": [
                {
                    "id": "balance",
                    "label": "API balance",
                    "unit": "CNY",
                    "remaining": 88.5,
                }
            ],
            "models": [
                {
                    "model_id": "deepseek-chat",
                    "display_name": "DeepSeek Chat",
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "cost": 0.15,
                    "currency": "CNY",
                }
            ],
        }

        snapshots = load_snapshots([raw])

        self.assertEqual(snapshots[0].requests_today, 42)
        self.assertEqual(snapshots[0].models[0].model_id, "deepseek-chat")
        self.assertEqual(snapshots[0].to_dict()["quotas"][0]["remaining"], 88.5)


if __name__ == "__main__":
    unittest.main()
