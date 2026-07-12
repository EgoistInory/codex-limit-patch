from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_limit_patch.usage_monitor.models import AccountSnapshot
from codex_limit_patch.usage_monitor.multi_live_demo import build_multi_live_payload
from codex_limit_patch.usage_monitor.providers.base import (
    FetchAttempt,
    ProviderDescriptor,
    ProviderFetchOutcome,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "demos" / "milestone-1" / "snapshots.json"
MILESTONE_THREE = ROOT / "demos" / "milestone-3"
NOW = datetime(2026, 7, 11, 8, 0, 0, tzinfo=timezone.utc)


def outcome(provider_id: str, provider_name: str, client_name: str) -> ProviderFetchOutcome:
    descriptor = ProviderDescriptor(
        id=provider_id,
        display_name=provider_name,
        client_name=client_name,
        account_kind="subscription" if provider_id == "openai" else "local_estimate",
        stale_after_seconds=300,
    )
    snapshot = AccountSnapshot.from_dict(
        {
            "id": "%s-live" % provider_id,
            "provider_id": provider_id,
            "provider_name": provider_name,
            "client_name": client_name,
            "account_kind": descriptor.account_kind,
            "status": "available",
            "source_type": "local_client" if provider_id == "openai" else "local_logs",
            "source_label": (
                "Codex app-server"
                if provider_id == "openai"
                else "Claude Code local logs"
            ),
            "fetched_at": "2026-07-11T08:00:00Z",
            "stale_after_seconds": 300,
            "quotas": [],
            "models": [],
        }
    )
    attempt = FetchAttempt(
        strategy_id="%s.strategy" % provider_id,
        source_type=snapshot.source_type,
        source_label=snapshot.source_label,
        available=True,
        success=True,
    )
    return ProviderFetchOutcome(descriptor, snapshot, (attempt,))


class MultiLiveDemoTests(unittest.TestCase):
    def test_payload_replaces_openai_and_anthropic_only(self) -> None:
        payload = build_multi_live_payload(
            FIXTURE,
            outcomes=[
                outcome("openai", "OpenAI", "Codex"),
                outcome("anthropic", "Anthropic", "Claude Code"),
            ],
            now=NOW,
        )

        self.assertEqual(payload["live_provider_ids"], ["openai", "anthropic"])
        by_provider = {item["provider_id"]: item for item in payload["accounts"]}
        self.assertFalse(by_provider["openai"]["demo"])
        self.assertFalse(by_provider["anthropic"]["demo"])
        self.assertTrue(by_provider["deepseek"]["demo"])
        self.assertTrue(by_provider["zhipu"]["demo"])
        self.assertTrue(by_provider["xiaomi"]["demo"])

    def test_payload_preserves_fixture_order_and_attempts(self) -> None:
        payload = build_multi_live_payload(
            FIXTURE,
            outcomes=[
                outcome("openai", "OpenAI", "Codex"),
                outcome("anthropic", "Anthropic", "Claude Code"),
            ],
            now=NOW,
        )

        self.assertEqual(
            [item["provider_id"] for item in payload["accounts"]],
            ["openai", "anthropic", "deepseek", "zhipu", "xiaomi"],
        )
        self.assertTrue(payload["fetch_attempts"]["openai"][0]["success"])
        self.assertTrue(payload["fetch_attempts"]["anthropic"][0]["success"])

    def test_milestone_three_has_example_and_live_entrypoints(self) -> None:
        example = (MILESTONE_THREE / "index.html").read_text(encoding="utf-8")
        live = (MILESTONE_THREE / "index-live.html").read_text(encoding="utf-8")

        self.assertIn("demo-data.example.js", example)
        self.assertIn("demo-data.js", live)
        self.assertTrue((MILESTONE_THREE / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
