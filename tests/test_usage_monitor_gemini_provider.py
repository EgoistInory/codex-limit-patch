from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_limit_patch.usage_monitor.gemini_logs import GeminiModelTotals, GeminiUsageTotals
from codex_limit_patch.usage_monitor.providers.gemini import (
    GeminiLocalLogsStrategy,
    fetch_gemini_outcome,
)


NOW = datetime(2026, 7, 14, 2, 0, 0, tzinfo=timezone.utc)


class GeminiProviderTests(unittest.TestCase):
    def test_maps_local_totals_without_claiming_quota(self) -> None:
        totals = GeminiUsageTotals(
            requests=2,
            input_tokens=140,
            output_tokens=30,
            cached_tokens=30,
            thoughts_tokens=5,
            tool_tokens=2,
            total_tokens=207,
            models=(
                GeminiModelTotals("gemini-3-pro", 1, 100, 20, 30, 5, 2, 157),
                GeminiModelTotals("gemini-3-flash", 1, 40, 10, 0, 0, 0, 50),
            ),
        )
        with TemporaryDirectory() as temp_dir:
            sessions = Path(temp_dir) / "tmp"
            sessions.mkdir()
            strategy = GeminiLocalLogsStrategy(
                config_dir=Path(temp_dir),
                scanner=lambda *_args, **_kwargs: totals,
            )

            snapshot = strategy.fetch(NOW)

        self.assertEqual(snapshot.provider_id, "google")
        self.assertEqual(snapshot.client_name, "Gemini CLI")
        self.assertEqual(snapshot.account_kind, "local_estimate")
        self.assertEqual(snapshot.tokens_today, 207)
        self.assertEqual(snapshot.requests_today, 2)
        self.assertEqual(snapshot.quotas, ())
        self.assertIn("Local usage only", snapshot.message)

    def test_missing_session_directory_is_not_configured(self) -> None:
        with TemporaryDirectory() as temp_dir:
            outcome = fetch_gemini_outcome(config_dir=Path(temp_dir), now=NOW)

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertFalse(outcome.attempts[0].available)


if __name__ == "__main__":
    unittest.main()
