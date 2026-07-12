from __future__ import annotations

import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.models import AccountSnapshot
from codex_limit_patch.usage_monitor.providers.base import (
    ProviderDescriptor,
    run_provider,
)


NOW = datetime(2026, 7, 11, 4, 0, 0, tzinfo=timezone.utc)
DESCRIPTOR = ProviderDescriptor(
    id="example",
    display_name="Example AI",
    client_name="Example CLI",
    account_kind="subscription",
    stale_after_seconds=300,
)


def snapshot(source_label: str) -> AccountSnapshot:
    return AccountSnapshot.from_dict(
        {
            "id": "example-main",
            "provider_id": "example",
            "provider_name": "Example AI",
            "client_name": "Example CLI",
            "account_kind": "subscription",
            "status": "available",
            "source_type": "local_client",
            "source_label": source_label,
            "fetched_at": "2026-07-11T04:00:00Z",
            "stale_after_seconds": 300,
            "quotas": [],
            "models": [],
        }
    )


class FailingStrategy:
    id = "example.failing"
    source_type = "local_client"
    source_label = "Failing source"

    def is_available(self) -> bool:
        return True

    def fetch(self, now: datetime) -> AccountSnapshot:
        raise RuntimeError("source failed")


class WorkingStrategy:
    id = "example.working"
    source_type = "official_api"
    source_label = "Working source"

    def is_available(self) -> bool:
        return True

    def fetch(self, now: datetime) -> AccountSnapshot:
        return snapshot(self.source_label)


class SecretFailingStrategy:
    id = "example.secret"
    source_type = "official_api"
    source_label = "Secret source"

    def is_available(self) -> bool:
        return True

    def fetch(self, now: datetime) -> AccountSnapshot:
        raise RuntimeError("request failed token=sk-sensitive\nraw response follows")


class DisabledStrategy:
    id = "example.disabled"
    source_type = "official_api"
    source_label = "Disabled source"

    def is_available(self) -> bool:
        return False

    def fetch(self, now: datetime) -> AccountSnapshot:
        raise AssertionError("disabled strategy must not run")


class ProviderRunnerTests(unittest.TestCase):
    def test_runner_falls_back_to_second_available_strategy(self) -> None:
        outcome = run_provider(
            DESCRIPTOR,
            [FailingStrategy(), WorkingStrategy()],
            now=NOW,
        )

        self.assertEqual(outcome.snapshot.source_label, "Working source")
        self.assertEqual([attempt.success for attempt in outcome.attempts], [False, True])

    def test_runner_returns_unavailable_snapshot_without_secret_or_multiline_error(self) -> None:
        outcome = run_provider(DESCRIPTOR, [SecretFailingStrategy()], now=NOW)

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertNotIn("sk-sensitive", outcome.snapshot.message)
        self.assertNotIn("\n", outcome.snapshot.message)
        self.assertIn("[redacted]", outcome.snapshot.message)

    def test_runner_skips_disabled_strategy(self) -> None:
        outcome = run_provider(
            DESCRIPTOR,
            [DisabledStrategy(), WorkingStrategy()],
            now=NOW,
        )

        self.assertEqual(len(outcome.attempts), 2)
        self.assertFalse(outcome.attempts[0].available)
        self.assertTrue(outcome.attempts[1].success)


if __name__ == "__main__":
    unittest.main()
