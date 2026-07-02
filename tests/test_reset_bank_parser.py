from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codex_limit_patch.display import render_expanded, render_pill
from codex_limit_patch.local_probe import probe_local_safe_sources
from codex_limit_patch.parser import (
    build_codex_limit_state,
    normalize_reset_bank,
    normalize_timestamp,
)


NOW = datetime(2026, 7, 2, 10, 0, 0, tzinfo=timezone.utc)


class ResetBankParserTests(unittest.TestCase):
    def test_only_available_count(self) -> None:
        state = normalize_reset_bank({"availableCount": 2}, snapshot_at=NOW, now=NOW)

        self.assertEqual(state.availableCount, 2)
        self.assertFalse(state.detailsAvailable)
        self.assertEqual(state.credits, [])

    def test_available_count_zero(self) -> None:
        state = normalize_reset_bank({"availableCount": 0}, snapshot_at=NOW, now=NOW)

        self.assertEqual(state.availableCount, 0)
        self.assertFalse(state.detailsAvailable)

    def test_null_reset_bank(self) -> None:
        state = normalize_reset_bank(None, snapshot_at=NOW, now=NOW)

        self.assertFalse(state.detailsAvailable)
        self.assertEqual(state.errorMessage, "Reset bank data not provided")

    def test_credits_array_details(self) -> None:
        state = normalize_reset_bank(
            {
                "credits": [
                    {
                        "id": "credit-1",
                        "status": "available",
                        "reason": "referral bonus",
                        "earnedAt": "2026-07-01T10:22:00Z",
                        "expiresAt": "2026-07-31T23:59:00Z",
                    }
                ]
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertTrue(state.detailsAvailable)
        self.assertEqual(state.availableCount, 1)
        self.assertEqual(state.totalCount, 1)
        self.assertEqual(state.credits[0].source, "referral")
        self.assertEqual(state.credits[0].acquiredAt, "2026-07-01T10:22:00Z")

    def test_items_array_details(self) -> None:
        state = normalize_reset_bank(
            {
                "items": [
                    {
                        "status": "active",
                        "source": "official compensation",
                        "grantedAt": "2026-07-01T00:00:00Z",
                    }
                ]
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.credits[0].status, "available")
        self.assertEqual(state.credits[0].source, "official_grant")

    def test_unix_seconds_expires_at(self) -> None:
        iso = normalize_timestamp(1785600000)

        self.assertEqual(iso, "2026-08-01T16:00:00Z")

    def test_unix_milliseconds_expires_at(self) -> None:
        iso = normalize_timestamp(1785600000000)

        self.assertEqual(iso, "2026-08-01T16:00:00Z")

    def test_iso_string_expires_at(self) -> None:
        iso = normalize_timestamp("2026-08-01T23:59:00Z")

        self.assertEqual(iso, "2026-08-01T23:59:00Z")

    def test_acquired_priority(self) -> None:
        state = normalize_reset_bank(
            {
                "credits": [
                    {
                        "acquiredAt": "2026-07-02T01:00:00Z",
                        "earnedAt": "2026-07-01T01:00:00Z",
                        "grantedAt": "2026-06-30T01:00:00Z",
                    }
                ]
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.credits[0].acquiredAt, "2026-07-02T01:00:00Z")

    def test_earned_priority_over_granted(self) -> None:
        state = normalize_reset_bank(
            {
                "credits": [
                    {
                        "earnedAt": "2026-07-01T01:00:00Z",
                        "grantedAt": "2026-06-30T01:00:00Z",
                    }
                ]
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.credits[0].acquiredAt, "2026-07-01T01:00:00Z")

    def test_redeemed_maps_to_used(self) -> None:
        state = normalize_reset_bank(
            {"credits": [{"status": "redeemed"}]},
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.credits[0].status, "used")

    def test_consumed_maps_to_used(self) -> None:
        state = normalize_reset_bank(
            {"credits": [{"status": "consumed"}]},
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.credits[0].status, "used")

    def test_expires_before_now_maps_to_expired_without_status(self) -> None:
        state = normalize_reset_bank(
            {"credits": [{"expiresAt": "2026-07-01T00:00:00Z"}]},
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.credits[0].status, "expired")

    def test_available_count_warning_when_detail_differs(self) -> None:
        state = normalize_reset_bank(
            {
                "availableCount": 2,
                "credits": [
                    {"status": "available"},
                    {"status": "used"},
                ],
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.availableCount, 2)
        self.assertEqual(
            state.warningMessage,
            "Detail count may differ from backend snapshot",
        )

    def test_unknown_fields_do_not_crash(self) -> None:
        state = normalize_reset_bank(
            {"mystery": {"nested": ["value"]}},
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertIsNone(state.availableCount)
        self.assertFalse(state.detailsAvailable)

    def test_build_state_from_app_server_response(self) -> None:
        state = build_codex_limit_state(
            {
                "result": {
                    "rateLimits": {
                        "primary": {"usedPercent": 78},
                        "secondary": {"usedPercent": 64},
                        "planType": "plus",
                    },
                    "rateLimitResetCredits": {"availableCount": 2},
                }
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertEqual(state.resetCredits, 2)
        self.assertEqual(state.planName, "plus")
        self.assertEqual(state.fiveHour.usedPercent, 78)
        self.assertEqual(state.weekly.usedPercent, 64)

    def test_display_uses_remaining_percent_and_reset_times(self) -> None:
        state = build_codex_limit_state(
            {
                "result": {
                    "rateLimits": {
                        "primary": {
                            "usedPercent": 23,
                            "resetsAt": "2026-07-02T12:59:22Z",
                        },
                        "secondary": {
                            "usedPercent": 20,
                            "resetsAt": "2026-07-09T01:35:59Z",
                        },
                    },
                    "rateLimitResetCredits": {"availableCount": 0},
                }
            },
            snapshot_at=NOW,
            now=NOW,
        )

        self.assertIn("Codex 5h 77%", render_pill(state))
        expanded = render_expanded(state)
        self.assertIn("Codex 5h remaining: 77%", expanded)
        self.assertIn("Codex 5h resets at:", expanded)
        self.assertIn("Weekly remaining: 80%", expanded)

    def test_local_safe_probe_finds_detail_json_line(self) -> None:
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            sessions = codex_home / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "rollout.jsonl").write_text(
                '{"event":"x","rateLimitResetCredits":{"availableCount":1,'
                '"credits":[{"status":"available","granted_at":"2026-06-17T09:38:00Z",'
                '"expires_at":"2026-07-17T09:38:00Z"}]}}\n',
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}):
                state = probe_local_safe_sources(snapshot_at=NOW, now=NOW)

        self.assertIsNotNone(state)
        self.assertTrue(state.detailsAvailable)
        self.assertEqual(state.availableCount, 1)
        self.assertEqual(state.credits[0].grantedAt, "2026-06-17T09:38:00Z")
        self.assertEqual(state.credits[0].expiresAt, "2026-07-17T09:38:00Z")

    def test_local_safe_probe_ignores_count_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            sessions = codex_home / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "rollout.jsonl").write_text(
                '{"rateLimitResetCredits":{"availableCount":2}}\n',
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}):
                state = probe_local_safe_sources(snapshot_at=NOW, now=NOW)

        self.assertIsNone(state)


if __name__ == "__main__":
    unittest.main()
