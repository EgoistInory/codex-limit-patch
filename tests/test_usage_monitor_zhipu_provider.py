from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.providers.zhipu import (
    ZhipuQuotaClient,
    ZhipuQuotaStrategy,
    fetch_zhipu_outcome,
    parse_zhipu_quota,
)


NOW = datetime(2026, 7, 14, 2, 0, 0, tzinfo=timezone.utc)
PAYLOAD = {
    "code": 200,
    "success": True,
    "data": {
        "planName": "Pro",
        "limits": [
            {
                "type": "TIME_LIMIT",
                "unit": 5,
                "number": 1,
                "usage": 1000,
                "currentValue": 147,
                "remaining": 853,
                "percentage": 14,
                "nextResetTime": 1784706344993,
                "usageDetails": [],
            },
            {
                "type": "TOKENS_LIMIT",
                "unit": 3,
                "number": 5,
                "usage": 1000000,
                "currentValue": 80000,
                "remaining": 920000,
                "percentage": 8,
                "nextResetTime": 1783049703178,
            },
            {
                "type": "TOKENS_LIMIT",
                "unit": 6,
                "number": 1,
                "usage": 10000000,
                "currentValue": 700000,
                "remaining": 9300000,
                "percentage": 7,
                "nextResetTime": 1783496744998,
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


class ZhipuProviderTests(unittest.TestCase):
    def test_parser_maps_token_windows_before_time_quota(self) -> None:
        snapshot = parse_zhipu_quota(PAYLOAD, now=NOW)

        self.assertEqual(snapshot.provider_id, "zhipu")
        self.assertEqual(snapshot.plan_name, "Pro")
        self.assertEqual([quota.label for quota in snapshot.quotas], [
            "5-hour token quota",
            "Weekly token quota",
            "MCP/time quota",
        ])
        self.assertEqual(snapshot.quotas[0].remaining_percent, 92)
        self.assertEqual(snapshot.quotas[1].remaining_percent, 93)
        self.assertEqual(snapshot.quotas[2].remaining_percent, 85.3)
        self.assertEqual(snapshot.quotas[0].resets_at, "2026-07-03T03:35:03.178000Z")

    def test_strategy_uses_key_without_serializing_it(self) -> None:
        secret = "zhipu-sensitive-key"
        client = FakeClient(PAYLOAD)

        snapshot = ZhipuQuotaStrategy(api_key=secret, client=client).fetch(NOW)

        self.assertEqual(client.received_key, secret)
        self.assertNotIn(secret, json.dumps(snapshot.to_dict()))

    def test_missing_key_returns_unavailable_outcome(self) -> None:
        outcome = fetch_zhipu_outcome(api_key="", now=NOW, environ={})

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertFalse(outcome.attempts[0].available)

    def test_client_enforces_endpoint_authorization_and_size(self) -> None:
        observed = {}

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["authorization"] = request.get_header("Authorization")
            observed["timeout"] = timeout
            return FakeResponse(json.dumps(PAYLOAD).encode("utf-8"))

        client = ZhipuQuotaClient(opener=opener)

        self.assertEqual(client.fetch("zhipu-test"), PAYLOAD)
        self.assertEqual(
            observed["url"],
            "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
        )
        self.assertEqual(observed["authorization"], "Bearer zhipu-test")
        self.assertEqual(observed["timeout"], 10.0)
        with self.assertRaisesRegex(ValueError, "official"):
            ZhipuQuotaClient(endpoint="https://example.com/api/monitor/usage/quota/limit")
        oversized = b"x" * (1024 * 1024 + 1)
        client = ZhipuQuotaClient(
            opener=lambda _request, **_kwargs: FakeResponse(oversized)
        )
        with self.assertRaisesRegex(RuntimeError, "too large"):
            client.fetch("zhipu-test")


if __name__ == "__main__":
    unittest.main()
