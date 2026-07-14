from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_limit_patch.usage_monitor.collector import (
    collect_supported_payload,
    collect_three_source_payload,
)
from codex_limit_patch.usage_monitor.models import AccountSnapshot
from codex_limit_patch.usage_monitor.providers.base import (
    FetchAttempt,
    ProviderDescriptor,
    ProviderFetchOutcome,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "demos" / "milestone-1" / "snapshots.json"
NOW = datetime(2026, 7, 13, 2, 0, 0, tzinfo=timezone.utc)


def outcome(provider_id: str) -> ProviderFetchOutcome:
    descriptor = ProviderDescriptor(
        id=provider_id,
        display_name=provider_id.title(),
        client_name=None,
        account_kind="api",
        stale_after_seconds=300,
    )
    snapshot = AccountSnapshot.from_dict(
        {
            "id": "%s-live" % provider_id,
            "provider_id": provider_id,
            "provider_name": descriptor.display_name,
            "client_name": None,
            "account_kind": "api",
            "status": "available",
            "source_type": "test",
            "source_label": "%s test" % provider_id,
            "fetched_at": "2026-07-13T02:00:00Z",
            "stale_after_seconds": 300,
            "quotas": [],
            "models": [],
        }
    )
    attempt = FetchAttempt(
        strategy_id="%s.test" % provider_id,
        source_type="test",
        source_label=snapshot.source_label,
        available=True,
        success=True,
    )
    return ProviderFetchOutcome(descriptor, snapshot, (attempt,))


class UsageMonitorCollectorTests(unittest.TestCase):
    def test_collects_three_sources_with_shared_timestamp_and_options(self) -> None:
        calls = []
        deepseek_environ = {"DEEPSEEK_API_KEY": "not-serialized"}

        def codex_fetcher(*, codex_bin, now):
            calls.append(("openai", codex_bin, now))
            return outcome("openai")

        def claude_fetcher(*, config_dir, now):
            calls.append(("anthropic", config_dir, now))
            return outcome("anthropic")

        def deepseek_fetcher(api_key, *, environ, now):
            calls.append(("deepseek", api_key, environ, now))
            return outcome("deepseek")

        payload = collect_three_source_payload(
            FIXTURE,
            codex_bin="/tmp/codex",
            claude_config_dir=Path("/tmp/claude"),
            deepseek_api_key="memory-only",
            deepseek_environ=deepseek_environ,
            now=NOW,
            codex_fetcher=codex_fetcher,
            claude_fetcher=claude_fetcher,
            deepseek_fetcher=deepseek_fetcher,
        )

        self.assertEqual(payload["live_provider_ids"], ["openai", "anthropic", "deepseek"])
        self.assertEqual(calls[0], ("openai", "/tmp/codex", NOW))
        self.assertEqual(calls[1], ("anthropic", Path("/tmp/claude"), NOW))
        self.assertEqual(
            calls[2],
            ("deepseek", "memory-only", deepseek_environ, NOW),
        )
        self.assertNotIn("memory-only", str(payload))

    def test_collects_supported_providers_in_stable_order(self) -> None:
        calls = []

        def local_fetcher(provider_id, option_name):
            def fetcher(**kwargs):
                calls.append((provider_id, option_name, kwargs))
                return outcome(provider_id)

            return fetcher

        def api_fetcher(provider_id):
            def fetcher(api_key, *, environ, now):
                calls.append((provider_id, api_key, environ, now))
                return outcome(provider_id)

            return fetcher

        payload = collect_supported_payload(
            FIXTURE,
            codex_bin="/tmp/codex",
            claude_config_dir=Path("/tmp/claude"),
            gemini_config_dir=Path("/tmp/gemini"),
            deepseek_api_key="deepseek-memory",
            kimi_api_key="kimi-memory",
            zhipu_api_key="zhipu-memory",
            minimax_api_key="minimax-memory",
            api_environ={},
            now=NOW,
            codex_fetcher=local_fetcher("openai", "codex_bin"),
            claude_fetcher=local_fetcher("anthropic", "config_dir"),
            gemini_fetcher=local_fetcher("google", "config_dir"),
            deepseek_fetcher=api_fetcher("deepseek"),
            kimi_fetcher=api_fetcher("kimi"),
            zhipu_fetcher=api_fetcher("zhipu"),
            minimax_fetcher=api_fetcher("minimax"),
        )

        self.assertEqual(
            payload["live_provider_ids"],
            ["openai", "anthropic", "google", "deepseek", "kimi", "zhipu", "minimax"],
        )
        self.assertEqual(payload["generated_at"], "2026-07-13T02:00:00Z")
        self.assertEqual([call[0] for call in calls], payload["live_provider_ids"])
        for secret in ("deepseek-memory", "kimi-memory", "zhipu-memory", "minimax-memory"):
            self.assertNotIn(secret, str(payload))


if __name__ == "__main__":
    unittest.main()
