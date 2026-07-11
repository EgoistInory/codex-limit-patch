from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_limit_patch.usage_monitor.claude_logs import (
    ClaudeModelTotals,
    ClaudeUsageTotals,
)
from codex_limit_patch.usage_monitor.providers.claude import (
    ClaudeLocalLogsStrategy,
    fetch_claude_outcome,
)


NOW = datetime(2026, 7, 11, 8, 0, 0, tzinfo=timezone.utc)
TOTALS = ClaudeUsageTotals(
    requests=3,
    input_tokens=100,
    output_tokens=50,
    cache_read_tokens=400,
    cache_creation_tokens=20,
    models=(
        ClaudeModelTotals(
            model_id="claude-opus-4-7",
            requests=3,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=400,
            cache_creation_tokens=20,
        ),
    ),
    files_scanned=2,
)


class ClaudeUsageProviderTests(unittest.TestCase):
    def test_strategy_maps_local_totals_without_quota_windows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            projects = Path(temp_dir) / "projects"
            projects.mkdir()

            snapshot = ClaudeLocalLogsStrategy(
                projects_dir=projects,
                scanner=lambda _path, **_kwargs: TOTALS,
            ).fetch(NOW)

        self.assertEqual(snapshot.provider_id, "anthropic")
        self.assertEqual(snapshot.client_name, "Claude Code")
        self.assertEqual(snapshot.account_kind, "local_estimate")
        self.assertEqual(snapshot.source_label, "Claude Code local logs")
        self.assertEqual(snapshot.requests_today, 3)
        self.assertEqual(snapshot.tokens_today, 570)
        self.assertEqual(snapshot.quotas, ())
        self.assertEqual(snapshot.models[0].cache_read_tokens, 400)
        self.assertIn("subscription limits", snapshot.message)

    def test_strategy_uses_local_midnight_as_period_start(self) -> None:
        observed = {}

        def scanner(_path, *, start, end):
            observed["start"] = start
            observed["end"] = end
            return TOTALS

        with TemporaryDirectory() as temp_dir:
            projects = Path(temp_dir) / "projects"
            projects.mkdir()
            ClaudeLocalLogsStrategy(projects_dir=projects, scanner=scanner).fetch(NOW)

        local_now = NOW.astimezone()
        self.assertEqual(observed["start"].astimezone().date(), local_now.date())
        self.assertEqual(observed["start"].astimezone().hour, 0)
        self.assertEqual(observed["end"], NOW)

    def test_missing_projects_directory_returns_unavailable_outcome(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing-projects"

            outcome = fetch_claude_outcome(projects_dir=missing, now=NOW)

        self.assertEqual(outcome.snapshot.status, "unavailable")
        self.assertFalse(outcome.attempts[0].available)
        self.assertNotIn(str(missing), outcome.snapshot.message)


if __name__ == "__main__":
    unittest.main()
