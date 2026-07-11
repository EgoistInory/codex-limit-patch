from __future__ import annotations

import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.alerts import evaluate_alerts
from codex_limit_patch.usage_monitor.models import AccountSnapshot


NOW = datetime(2026, 7, 11, 3, 0, 0, tzinfo=timezone.utc)


def make_snapshot(
    *,
    remaining_percent=50,
    remaining=None,
    unit="percent",
    status="available",
    fetched_at="2026-07-11T03:00:00Z",
    stale_after_seconds=300,
) -> AccountSnapshot:
    return AccountSnapshot.from_dict(
        {
            "id": "provider-main",
            "provider_id": "provider",
            "provider_name": "Provider",
            "account_kind": "subscription",
            "status": status,
            "source_type": "local_client",
            "source_label": "Local client",
            "fetched_at": fetched_at,
            "stale_after_seconds": stale_after_seconds,
            "quotas": [
                {
                    "id": "primary",
                    "label": "Primary window",
                    "unit": unit,
                    "remaining": remaining,
                    "remaining_percent": remaining_percent,
                }
            ],
            "models": [],
        }
    )


class UsageMonitorAlertTests(unittest.TestCase):
    def test_ten_percent_remaining_is_critical(self) -> None:
        alerts = evaluate_alerts(make_snapshot(remaining_percent=10), now=NOW)

        self.assertEqual(alerts[0].severity, "critical")
        self.assertEqual(alerts[0].kind, "quota")

    def test_twenty_percent_remaining_is_warning(self) -> None:
        alerts = evaluate_alerts(make_snapshot(remaining_percent=20), now=NOW)

        self.assertEqual(alerts[0].severity, "warning")

    def test_old_snapshot_is_stale(self) -> None:
        snapshot = make_snapshot(
            fetched_at="2026-07-11T01:00:00Z",
            stale_after_seconds=300,
        )

        alerts = evaluate_alerts(snapshot, now=NOW)

        self.assertTrue(any(alert.kind == "stale" for alert in alerts))

    def test_unknown_quota_does_not_create_fake_alert(self) -> None:
        alerts = evaluate_alerts(make_snapshot(remaining_percent=None), now=NOW)

        self.assertFalse(any(alert.kind == "quota" for alert in alerts))

    def test_low_currency_balance_is_warning(self) -> None:
        snapshot = make_snapshot(
            remaining_percent=None,
            remaining=4.5,
            unit="CNY",
        )

        alerts = evaluate_alerts(snapshot, now=NOW, low_balance=10)

        self.assertTrue(any(alert.kind == "balance" for alert in alerts))

    def test_unavailable_source_is_critical(self) -> None:
        alerts = evaluate_alerts(
            make_snapshot(status="unavailable", remaining_percent=None),
            now=NOW,
        )

        self.assertEqual(alerts[0].kind, "unavailable")
        self.assertEqual(alerts[0].severity, "critical")


if __name__ == "__main__":
    unittest.main()
