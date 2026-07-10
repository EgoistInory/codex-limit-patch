from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codex_limit_patch import cli, local_probe
from codex_limit_patch.client import CodexAppServerError
from codex_limit_patch.display import render_expanded, render_pill

from codex_limit_patch.parser import build_codex_limit_state


NOW = datetime(2026, 7, 10, 10, 0, 0, tzinfo=timezone.utc)


class RateLimitFallbackTests(unittest.TestCase):
    def test_probe_converts_latest_rollout_rate_limits(self) -> None:
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            sessions = codex_home / "sessions"
            sessions.mkdir(parents=True)
            rollout = sessions / "rollout-test.jsonl"
            rows = [
                {
                    "timestamp": "2026-07-10T08:00:00Z",
                    "type": "event_msg",
                    "payload": {
                        "rate_limits": {
                            "primary": {"used_percent": 50, "window_minutes": 300},
                            "plan_type": "plus",
                        }
                    },
                },
                {
                    "timestamp": "2026-07-10T09:30:00Z",
                    "type": "event_msg",
                    "payload": {
                        "rate_limits": {
                            "primary": {
                                "used_percent": 13,
                                "window_minutes": 300,
                                "resets_at": 1783693201,
                            },
                            "secondary": {
                                "used_percent": 18,
                                "window_minutes": 10080,
                                "resets_at": 1784248078,
                            },
                            "plan_type": "plus",
                            "rate_limit_reached_type": None,
                        }
                    },
                },
            ]
            rollout.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}):
                response = local_probe.probe_local_rate_limits()

        self.assertIsNotNone(response)
        self.assertEqual(response["result"]["rateLimits"]["primary"]["usedPercent"], 13)
        self.assertEqual(
            response["result"]["rateLimits"]["secondary"]["windowDurationMins"],
            10080,
        )
        self.assertEqual(response["result"]["rateLimits"]["planType"], "plus")
        self.assertEqual(
            response["_codexLimitPatch"]["snapshotAt"],
            "2026-07-10T09:30:00Z",
        )

    def test_read_falls_back_when_app_server_request_fails(self) -> None:
        fallback = {
            "result": {"rateLimits": {"primary": {"usedPercent": 13}}},
            "_codexLimitPatch": {
                "source": "local_rollout",
                "sourceLabel": "local Codex rollout cache",
                "snapshotAt": "2026-07-10T09:30:00Z",
                "stale": True,
            },
        }

        with patch(
            "codex_limit_patch.cli.CodexAppServerClient.read_rate_limits",
            side_effect=CodexAppServerError("ChatGPT usage endpoint timed out"),
        ), patch(
            "codex_limit_patch.cli.probe_local_rate_limits",
            return_value=fallback,
        ):
            response = cli._read_rate_limits(None, debug=None)

        self.assertEqual(response["result"]["rateLimits"]["primary"]["usedPercent"], 13)
        self.assertIn("timed out", response["_codexLimitPatch"]["warning"])

    def test_read_sanitizes_localized_os_error(self) -> None:
        fallback = {
            "result": {"rateLimits": {"primary": {"usedPercent": 13}}},
            "_codexLimitPatch": {"source": "local_rollout", "stale": True},
        }

        with patch(
            "codex_limit_patch.cli.CodexAppServerClient",
            side_effect=FileNotFoundError(2, "localized message"),
        ), patch(
            "codex_limit_patch.cli.probe_local_rate_limits",
            return_value=fallback,
        ):
            response = cli._read_rate_limits(None, debug=None)

        self.assertEqual(
            response["_codexLimitPatch"]["warning"],
            "Live rate limits unavailable: unable to start Codex binary (errno 2)",
        )
    def test_fallback_state_is_marked_stale_in_text_output(self) -> None:
        state = build_codex_limit_state(
            {
                "result": {
                    "rateLimits": {
                        "primary": {"usedPercent": 13},
                        "secondary": {"usedPercent": 18},
                        "planType": "plus",
                    }
                },
                "_codexLimitPatch": {
                    "source": "local_rollout",
                    "sourceLabel": "local Codex rollout cache",
                    "snapshotAt": "2026-07-10T09:30:00Z",
                    "stale": True,
                    "warning": "Live rate limits unavailable",
                },
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertTrue(state.stale)
        self.assertEqual(state.dataSource, "local_rollout")
        self.assertEqual(state.lastUpdatedAt, "2026-07-10T09:30:00Z")
        self.assertIn("cached", render_pill(state).lower())
        self.assertIn("local Codex rollout cache", render_expanded(state))


if __name__ == "__main__":
    unittest.main()
