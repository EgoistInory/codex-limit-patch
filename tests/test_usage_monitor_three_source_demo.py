from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_limit_patch.usage_monitor.models import AccountSnapshot
from codex_limit_patch.usage_monitor.providers.base import (
    FetchAttempt,
    ProviderDescriptor,
    ProviderFetchOutcome,
)
from codex_limit_patch.usage_monitor.providers.deepseek import fetch_deepseek_outcome
from codex_limit_patch.usage_monitor.three_source_demo import build_three_source_payload


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "demos" / "milestone-1" / "snapshots.json"
MILESTONE_FOUR = ROOT / "demos" / "milestone-4"
NOW = datetime(2026, 7, 12, 1, 0, 0, tzinfo=timezone.utc)


def successful_outcome(provider_id: str) -> ProviderFetchOutcome:
    names = {
        "openai": ("OpenAI", "Codex", "local_client"),
        "anthropic": ("Anthropic", "Claude Code", "local_logs"),
        "deepseek": ("DeepSeek", None, "official_api"),
    }
    provider_name, client_name, source_type = names[provider_id]
    descriptor = ProviderDescriptor(
        id=provider_id,
        display_name=provider_name,
        client_name=client_name,
        account_kind="api" if provider_id == "deepseek" else "subscription",
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
            "source_type": source_type,
            "source_label": "%s source" % provider_name,
            "fetched_at": "2026-07-12T01:00:00Z",
            "stale_after_seconds": 300,
            "quotas": [],
            "models": [],
        }
    )
    attempt = FetchAttempt(
        strategy_id="%s.strategy" % provider_id,
        source_type=source_type,
        source_label=snapshot.source_label,
        available=True,
        success=True,
    )
    return ProviderFetchOutcome(descriptor, snapshot, (attempt,))


class ThreeSourceDemoTests(unittest.TestCase):
    def test_payload_marks_three_live_providers_and_two_demo_rows(self) -> None:
        payload = build_three_source_payload(
            FIXTURE,
            outcomes=[
                successful_outcome("openai"),
                successful_outcome("anthropic"),
                successful_outcome("deepseek"),
            ],
            now=NOW,
        )

        self.assertEqual(
            payload["live_provider_ids"],
            ["openai", "anthropic", "deepseek"],
        )
        by_provider = {item["provider_id"]: item for item in payload["accounts"]}
        self.assertFalse(by_provider["openai"]["demo"])
        self.assertFalse(by_provider["anthropic"]["demo"])
        self.assertFalse(by_provider["deepseek"]["demo"])
        self.assertTrue(by_provider["zhipu"]["demo"])
        self.assertTrue(by_provider["xiaomi"]["demo"])

    def test_missing_deepseek_key_is_explicit_live_unavailable_row(self) -> None:
        unavailable = fetch_deepseek_outcome(environ={}, now=NOW)

        payload = build_three_source_payload(
            FIXTURE,
            outcomes=[
                successful_outcome("openai"),
                successful_outcome("anthropic"),
                unavailable,
            ],
            now=NOW,
        )

        deepseek = next(
            item for item in payload["accounts"] if item["provider_id"] == "deepseek"
        )
        self.assertFalse(deepseek["demo"])
        self.assertEqual(deepseek["status"], "unavailable")
        self.assertEqual(deepseek["source_label"], "No successful source")

    def test_milestone_four_has_example_and_live_entrypoints(self) -> None:
        example = (MILESTONE_FOUR / "index.html").read_text(encoding="utf-8")
        live = (MILESTONE_FOUR / "index-live.html").read_text(encoding="utf-8")

        self.assertIn("demo-data.example.js", example)
        self.assertIn("demo-data.js", live)
        self.assertIn('http-equiv="refresh"', live)
        self.assertIn('content="60"', live)
        self.assertTrue((MILESTONE_FOUR / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
