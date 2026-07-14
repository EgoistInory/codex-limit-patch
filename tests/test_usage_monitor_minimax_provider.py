from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.providers.minimax import (
    MiniMaxQuotaClient,
    MiniMaxQuotaStrategy,
    fetch_minimax_outcome,
    parse_minimax_quota,
)


NOW = datetime(2026, 7, 14, 2, 0, 0, tzinfo=timezone.utc)
PAYLOAD = {
    "base_resp": {"status_code": 0, "status_msg": "success"},
    "data": {
        "current_subscribe_title": "Token Plan Plus",
        "model_remains": [
            {
                "model_name": "video",
                "current_interval_remaining_percent": 30,
            },
            {
                "model_name": "general",
                "current_interval_total_count": 0,
                "current_interval_usage_count": 0,
                "current_interval_remaining_percent": "96",
                "start_time": 1780279200000,
                "end_time": 1780297200000,
                "current_weekly_total_count": 0,
                "current_weekly_usage_count": 0,
                "current_weekly_remaining_percent": "99",
                "weekly_start_time": 1780243200000,
                "weekly_end_time": 1780848000000,
                "current_weekly_status": 1,
            },
        ],
    },
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


class MiniMaxProviderTests(unittest.TestCase):
    def test_parser_uses_general_rolling_and_weekly_lanes(self) -> None:
        snapshot = parse_minimax_quota(PAYLOAD, now=NOW)

        self.assertEqual(snapshot.provider_id, "minimax")
        self.assertEqual(snapshot.plan_name, "Token Plan Plus")
        self.assertEqual([quota.label for quota in snapshot.quotas], [
            "5-hour token quota",
            "Weekly token quota",
        ])
        self.assertEqual(snapshot.quotas[0].remaining_percent, 96)
        self.assertEqual(snapshot.quotas[1].remaining_percent, 99)
        self.assertEqual(snapshot.quotas[0].resets_at, "2026-06-01T07:00:00Z")

    def test_parser_falls_back_to_remaining_counts(self) -> None:
        payload = {
            "base_resp": {"status_code": 0},
            "model_remains": [
                {
                    "model_name": "general",
                    "current_interval_total_count": 1000,
                    "current_interval_usage_count": 250,
                    "start_time": 1780279200000,
                    "end_time": 1780297200000,
                }
            ],
        }

        snapshot = parse_minimax_quota(payload, now=NOW)

        self.assertEqual(snapshot.quotas[0].remaining, 250)
        self.assertEqual(snapshot.quotas[0].used, 750)
        self.assertEqual(snapshot.quotas[0].remaining_percent, 25)

    def test_strategy_uses_key_without_serializing_it(self) -> None:
        secret = "minimax-sensitive-key"
        client = FakeClient(PAYLOAD)

        snapshot = MiniMaxQuotaStrategy(api_key=secret, client=client).fetch(NOW)

        self.assertEqual(client.received_key, secret)
        self.assertNotIn(secret, json.dumps(snapshot.to_dict()))

    def test_missing_key_returns_unavailable_outcome(self) -> None:
        outcome = fetch_minimax_outcome(api_key="", now=NOW, environ={})

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertFalse(outcome.attempts[0].available)

    def test_client_enforces_endpoint_authorization_and_size(self) -> None:
        observed = {}

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["authorization"] = request.get_header("Authorization")
            observed["timeout"] = timeout
            return FakeResponse(json.dumps(PAYLOAD).encode("utf-8"))

        client = MiniMaxQuotaClient(opener=opener)

        self.assertEqual(client.fetch("minimax-test"), PAYLOAD)
        self.assertEqual(
            observed["url"],
            "https://www.minimax.io/v1/token_plan/remains",
        )
        self.assertEqual(observed["authorization"], "Bearer minimax-test")
        self.assertEqual(observed["timeout"], 10.0)
        with self.assertRaisesRegex(ValueError, "official"):
            MiniMaxQuotaClient(endpoint="https://example.com/v1/token_plan/remains")
        oversized = b"x" * (1024 * 1024 + 1)
        client = MiniMaxQuotaClient(
            opener=lambda _request, **_kwargs: FakeResponse(oversized)
        )
        with self.assertRaisesRegex(RuntimeError, "too large"):
            client.fetch("minimax-test")


if __name__ == "__main__":
    unittest.main()
