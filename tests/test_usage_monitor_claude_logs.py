from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_limit_patch.usage_monitor.claude_logs import (
    parse_claude_log_lines,
    scan_claude_projects,
)


START = datetime(2026, 7, 11, 0, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 12, 0, 0, 0, tzinfo=timezone.utc)


def assistant_line(message_id="msg-1", timestamp="2026-07-11T01:00:00Z") -> str:
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": timestamp,
            "cwd": "/private/project-name",
            "message": {
                "id": message_id,
                "model": "claude-opus-4-7",
                "content": [{"type": "text", "text": "private prompt response"}],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 400,
                },
            },
        }
    )


class ClaudeLogParserTests(unittest.TestCase):
    def test_parser_counts_assistant_usage_and_cache_tokens(self) -> None:
        totals = parse_claude_log_lines(
            [assistant_line()],
            start=START,
            end=END,
        )

        self.assertEqual(totals.requests, 1)
        self.assertEqual(totals.input_tokens, 100)
        self.assertEqual(totals.output_tokens, 50)
        self.assertEqual(totals.cache_creation_tokens, 20)
        self.assertEqual(totals.cache_read_tokens, 400)
        self.assertEqual(totals.total_tokens, 570)
        self.assertEqual(totals.models[0].model_id, "claude-opus-4-7")

    def test_parser_deduplicates_message_id(self) -> None:
        line = assistant_line()

        totals = parse_claude_log_lines([line, line], start=START, end=END)

        self.assertEqual(totals.requests, 1)
        self.assertEqual(totals.total_tokens, 570)

    def test_parser_ignores_unrelated_out_of_period_and_malformed_rows(self) -> None:
        user_line = json.dumps(
            {
                "type": "user",
                "timestamp": "2026-07-11T01:00:00Z",
                "message": {"content": "private user prompt"},
            }
        )
        old_line = assistant_line("msg-old", "2026-07-10T23:59:59Z")

        totals = parse_claude_log_lines(
            [user_line, old_line, "not-json"],
            start=START,
            end=END,
        )

        self.assertEqual(totals.requests, 0)
        self.assertEqual(totals.malformed_lines, 1)
        self.assertEqual(totals.ignored_lines, 2)

    def test_scanner_stays_inside_projects_root_and_skips_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            session_dir = root / "project-a"
            session_dir.mkdir(parents=True)
            (session_dir / "session.jsonl").write_text(
                assistant_line() + "\n",
                encoding="utf-8",
            )
            outside = Path(temp_dir) / "outside.jsonl"
            outside.write_text(assistant_line("outside") + "\n", encoding="utf-8")
            os.symlink(outside, session_dir / "linked.jsonl")

            totals = scan_claude_projects(root, start=START, end=END)

        self.assertEqual(totals.requests, 1)
        self.assertEqual(totals.files_scanned, 1)


if __name__ == "__main__":
    unittest.main()
