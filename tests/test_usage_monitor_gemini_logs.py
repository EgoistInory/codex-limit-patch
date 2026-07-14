from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_limit_patch.usage_monitor.gemini_logs import (
    parse_gemini_log_lines,
    scan_gemini_sessions,
)


START = datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 15, 0, 0, 0, tzinfo=timezone.utc)


class GeminiLogTests(unittest.TestCase):
    def test_sums_current_period_tokens_by_model(self) -> None:
        lines = [
            json.dumps({"sessionId": "session-1", "projectHash": "project"}),
            json.dumps(
                {
                    "id": "message-1",
                    "type": "gemini",
                    "timestamp": "2026-07-14T01:00:00Z",
                    "model": "gemini-3-pro",
                    "tokens": {
                        "input": 100,
                        "output": 20,
                        "cached": 30,
                        "thoughts": 5,
                        "tool": 2,
                        "total": 157,
                    },
                }
            ),
            json.dumps(
                {
                    "id": "message-2",
                    "type": "gemini",
                    "timestamp": "2026-07-14T02:00:00Z",
                    "model": "gemini-3-flash",
                    "tokens": {
                        "input": 40,
                        "output": 10,
                        "cached": 0,
                        "total": 50,
                    },
                }
            ),
        ]

        totals = parse_gemini_log_lines(lines, start=START, end=END)

        self.assertEqual(totals.requests, 2)
        self.assertEqual(totals.total_tokens, 207)
        self.assertEqual(totals.input_tokens, 140)
        self.assertEqual(totals.output_tokens, 30)
        self.assertEqual(totals.cached_tokens, 30)
        self.assertEqual([item.model_id for item in totals.models], [
            "gemini-3-pro",
            "gemini-3-flash",
        ])

    def test_ignores_out_of_period_and_malformed_records(self) -> None:
        lines = [
            "not-json",
            json.dumps(
                {
                    "id": "old",
                    "type": "gemini",
                    "timestamp": "2026-07-13T23:59:59Z",
                    "tokens": {"total": 100},
                }
            ),
            json.dumps(
                {
                    "id": "user",
                    "type": "user",
                    "timestamp": "2026-07-14T01:00:00Z",
                }
            ),
            json.dumps(
                {
                    "id": "bad-tokens",
                    "type": "gemini",
                    "timestamp": "2026-07-14T01:00:00Z",
                    "tokens": None,
                }
            ),
        ]

        totals = parse_gemini_log_lines(lines, start=START, end=END)

        self.assertEqual(totals.requests, 0)
        self.assertEqual(totals.total_tokens, 0)
        self.assertEqual(totals.malformed_lines, 1)
        self.assertEqual(totals.ignored_lines, 3)

    def test_scans_legacy_json_and_current_jsonl_sessions(self) -> None:
        message = {
            "id": "message-1",
            "type": "gemini",
            "timestamp": "2026-07-14T01:00:00Z",
            "model": "gemini-3-pro",
            "tokens": {"input": 10, "output": 5, "total": 15},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "project-a" / "chats" / "session-current.jsonl"
            current.parent.mkdir(parents=True)
            current.write_text(json.dumps(message) + "\n", encoding="utf-8")
            legacy = root / "project-b" / "chats" / "session-legacy.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps({"messages": [{**message, "id": "message-2"}]}),
                encoding="utf-8",
            )

            totals = scan_gemini_sessions(root, start=START, end=END)

        self.assertEqual(totals.requests, 2)
        self.assertEqual(totals.total_tokens, 30)
        self.assertEqual(totals.files_scanned, 2)


if __name__ == "__main__":
    unittest.main()
