from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from codex_limit_patch.usage_monitor.providers.deepseek import (
    DeepSeekBalanceClient,
    DeepSeekBalanceStrategy,
    fetch_deepseek_outcome,
    parse_deepseek_balance,
)


NOW = datetime(2026, 7, 12, 1, 0, 0, tzinfo=timezone.utc)
PAYLOAD = {
    "is_available": True,
    "balance_infos": [
        {
            "currency": "CNY",
            "total_balance": "110.00",
            "granted_balance": "10.00",
            "topped_up_balance": "100.00",
        },
        {
            "currency": "USD",
            "total_balance": "15.50",
            "granted_balance": "0.50",
            "topped_up_balance": "15.00",
        },
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


class FakeBalanceClient:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.received_key = None

    def fetch(self, api_key: str):
        self.received_key = api_key
        return self.payload


class DeepSeekProviderTests(unittest.TestCase):
    def test_parser_maps_multi_currency_balance_and_components(self) -> None:
        snapshot = parse_deepseek_balance(PAYLOAD, now=NOW)

        self.assertEqual(snapshot.status, "available")
        self.assertEqual([quota.unit for quota in snapshot.quotas], ["CNY", "USD"])
        self.assertEqual(snapshot.quotas[0].remaining, 110.0)
        self.assertIsNone(snapshot.quotas[0].remaining_percent)
        self.assertEqual(snapshot.quotas[0].components[0].label, "Granted")
        self.assertEqual(snapshot.quotas[0].components[1].label, "Paid")
        self.assertEqual(snapshot.quotas[0].components[1].value, 100.0)

    def test_parser_maps_unavailable_for_calls_to_degraded(self) -> None:
        payload = dict(PAYLOAD, is_available=False)

        snapshot = parse_deepseek_balance(payload, now=NOW)

        self.assertEqual(snapshot.status, "degraded")
        self.assertIn("unavailable for API calls", snapshot.message)

    def test_parser_rejects_invalid_decimal(self) -> None:
        payload = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "not-a-number",
                    "granted_balance": "0",
                    "topped_up_balance": "0",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "total_balance"):
            parse_deepseek_balance(payload, now=NOW)

    def test_strategy_uses_explicit_key_without_serializing_it(self) -> None:
        secret = "sk-test-sensitive"
        client = FakeBalanceClient(PAYLOAD)

        snapshot = DeepSeekBalanceStrategy(api_key=secret, client=client).fetch(NOW)

        self.assertEqual(client.received_key, secret)
        self.assertNotIn(secret, json.dumps(snapshot.to_dict()))

    def test_missing_key_returns_unavailable_outcome(self) -> None:
        outcome = fetch_deepseek_outcome(api_key="", now=NOW, environ={})

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertFalse(outcome.attempts[0].available)

    def test_client_builds_https_authorization_request_with_timeout(self) -> None:
        observed = {}

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["authorization"] = request.get_header("Authorization")
            observed["accept"] = request.get_header("Accept")
            observed["timeout"] = timeout
            return FakeResponse(json.dumps(PAYLOAD).encode("utf-8"))

        client = DeepSeekBalanceClient(opener=opener)

        result = client.fetch("sk-test")

        self.assertEqual(result, PAYLOAD)
        self.assertEqual(observed["url"], "https://api.deepseek.com/user/balance")
        self.assertEqual(observed["authorization"], "Bearer sk-test")
        self.assertEqual(observed["accept"], "application/json")
        self.assertEqual(observed["timeout"], 10.0)

    def test_client_rejects_non_https_endpoint_and_oversized_response(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            DeepSeekBalanceClient(endpoint="http://api.deepseek.com/user/balance")
        with self.assertRaisesRegex(ValueError, "official"):
            DeepSeekBalanceClient(
                endpoint="https://api.deepseek.com:444/user/balance"
            )
        with self.assertRaisesRegex(ValueError, "official"):
            DeepSeekBalanceClient(
                endpoint="https://user@api.deepseek.com/user/balance"
            )

        oversized = b"x" * (1024 * 1024 + 1)
        client = DeepSeekBalanceClient(opener=lambda _request, **_kwargs: FakeResponse(oversized))
        with self.assertRaisesRegex(RuntimeError, "too large"):
            client.fetch("sk-test")


if __name__ == "__main__":
    unittest.main()
