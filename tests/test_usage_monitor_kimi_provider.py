from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.providers.kimi import (
    KimiUsageClient,
    KimiUsageStrategy,
    fetch_kimi_outcome,
    parse_kimi_usage,
)


NOW = datetime(2026, 7, 14, 2, 0, 0, tzinfo=timezone.utc)
PAYLOAD = {
    "usage": {
        "limit": "2048",
        "used": "214",
        "remaining": "1834",
        "resetTime": "2026-07-20T00:00:00Z",
    },
    "limits": [
        {
            "window": {"duration": 300, "timeUnit": "TIME_UNIT_MINUTE"},
            "detail": {
                "limit": "200",
                "used": "139",
                "remaining": "61",
                "resetTime": "2026-07-14T04:30:00Z",
            },
        }
    ],
}


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self, size: int) -> bytes:
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeClient:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.received_key = None

    def fetch(self, api_key: str):
        self.received_key = api_key
        return self.payload


class KimiProviderTests(unittest.TestCase):
    def test_parser_maps_rolling_and_weekly_request_windows(self) -> None:
        snapshot = parse_kimi_usage(PAYLOAD, now=NOW)

        self.assertEqual(snapshot.provider_id, "kimi")
        self.assertEqual(snapshot.plan_name, "Kimi Code")
        self.assertEqual([quota.label for quota in snapshot.quotas], [
            "5-hour requests",
            "Weekly requests",
        ])
        self.assertEqual(snapshot.quotas[0].remaining, 61)
        self.assertAlmostEqual(snapshot.quotas[0].remaining_percent, 30.5)
        self.assertEqual(snapshot.quotas[0].resets_at, "2026-07-14T04:30:00Z")
        self.assertAlmostEqual(snapshot.quotas[1].remaining_percent, 89.55078125)

    def test_strategy_uses_explicit_key_without_serializing_it(self) -> None:
        secret = "kimi-sensitive-key"
        client = FakeClient(PAYLOAD)

        snapshot = KimiUsageStrategy(api_key=secret, client=client).fetch(NOW)

        self.assertEqual(client.received_key, secret)
        self.assertNotIn(secret, json.dumps(snapshot.to_dict()))

    def test_missing_key_returns_unavailable_outcome(self) -> None:
        outcome = fetch_kimi_outcome(api_key="", now=NOW, environ={})

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertFalse(outcome.attempts[0].available)

    def test_client_enforces_official_endpoint_and_request_bounds(self) -> None:
        observed = {}

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["authorization"] = request.get_header("Authorization")
            observed["timeout"] = timeout
            return FakeResponse(json.dumps(PAYLOAD).encode("utf-8"))

        client = KimiUsageClient(opener=opener)

        self.assertEqual(client.fetch("kimi-test"), PAYLOAD)
        self.assertEqual(observed["url"], "https://api.kimi.com/coding/v1/usages")
        self.assertEqual(observed["authorization"], "Bearer kimi-test")
        self.assertEqual(observed["timeout"], 10.0)
        with self.assertRaisesRegex(ValueError, "official"):
            KimiUsageClient(endpoint="https://example.com/coding/v1/usages")
        oversized = b"x" * (1024 * 1024 + 1)
        client = KimiUsageClient(
            opener=lambda _request, **_kwargs: FakeResponse(oversized)
        )
        with self.assertRaisesRegex(RuntimeError, "too large"):
            client.fetch("kimi-test")


if __name__ == "__main__":
    unittest.main()
