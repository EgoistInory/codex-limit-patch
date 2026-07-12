from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class ClaudeModelTotals:
    model_id: str
    requests: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


@dataclass(frozen=True)
class ClaudeUsageTotals:
    requests: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    models: Tuple[ClaudeModelTotals, ...]
    files_scanned: int = 0
    malformed_lines: int = 0
    ignored_lines: int = 0
    file_errors: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


class _Accumulator:
    def __init__(self, seen_ids: Set[str]) -> None:
        self.seen_ids = seen_ids
        self.requests = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_creation_tokens = 0
        self.models: Dict[str, Dict[str, int]] = {}
        self.files_scanned = 0
        self.malformed_lines = 0
        self.ignored_lines = 0
        self.file_errors = 0

    def add(
        self,
        *,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_creation_tokens: int,
    ) -> None:
        self.requests += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read_tokens
        self.cache_creation_tokens += cache_creation_tokens
        model = self.models.setdefault(
            model_id,
            {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            },
        )
        model["requests"] += 1
        model["input_tokens"] += input_tokens
        model["output_tokens"] += output_tokens
        model["cache_read_tokens"] += cache_read_tokens
        model["cache_creation_tokens"] += cache_creation_tokens

    def freeze(self) -> ClaudeUsageTotals:
        models = [
            ClaudeModelTotals(
                model_id=model_id,
                requests=values["requests"],
                input_tokens=values["input_tokens"],
                output_tokens=values["output_tokens"],
                cache_read_tokens=values["cache_read_tokens"],
                cache_creation_tokens=values["cache_creation_tokens"],
            )
            for model_id, values in self.models.items()
        ]
        models.sort(key=lambda item: (-item.total_tokens, item.model_id))
        return ClaudeUsageTotals(
            requests=self.requests,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            models=tuple(models),
            files_scanned=self.files_scanned,
            malformed_lines=self.malformed_lines,
            ignored_lines=self.ignored_lines,
            file_errors=self.file_errors,
        )


def parse_claude_log_lines(
    lines: Iterable[str],
    *,
    start: datetime,
    end: datetime,
    seen_ids: Optional[Set[str]] = None,
) -> ClaudeUsageTotals:
    accumulator = _Accumulator(seen_ids if seen_ids is not None else set())
    _consume_lines(accumulator, lines, start=_as_utc(start), end=_as_utc(end))
    return accumulator.freeze()


def scan_claude_projects(
    projects_dir: Path,
    *,
    start: datetime,
    end: datetime,
) -> ClaudeUsageTotals:
    root = projects_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError("Claude projects directory is not available")
    period_start = _as_utc(start)
    period_end = _as_utc(end)
    accumulator = _Accumulator(set())
    for candidate in sorted(root.rglob("*.jsonl")):
        if candidate.is_symlink():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            if resolved.parent != root and root not in resolved.parents:
                continue
            if resolved.stat().st_mtime < period_start.timestamp():
                continue
            with resolved.open("r", encoding="utf-8", errors="replace") as handle:
                _consume_lines(
                    accumulator,
                    handle,
                    start=period_start,
                    end=period_end,
                )
            accumulator.files_scanned += 1
        except OSError:
            accumulator.file_errors += 1
    return accumulator.freeze()


def _consume_lines(
    accumulator: _Accumulator,
    lines: Iterable[str],
    *,
    start: datetime,
    end: datetime,
) -> None:
    for line in lines:
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            accumulator.malformed_lines += 1
            continue
        if not isinstance(row, dict) or row.get("type") != "assistant":
            accumulator.ignored_lines += 1
            continue
        timestamp = _parse_timestamp(row.get("timestamp"))
        if timestamp is None:
            accumulator.malformed_lines += 1
            continue
        if timestamp < start or timestamp >= end:
            accumulator.ignored_lines += 1
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            accumulator.malformed_lines += 1
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            accumulator.ignored_lines += 1
            continue
        message_id = message.get("id")
        if isinstance(message_id, str) and message_id:
            if message_id in accumulator.seen_ids:
                accumulator.ignored_lines += 1
                continue
            accumulator.seen_ids.add(message_id)
        model = message.get("model")
        model_id = model if isinstance(model, str) and model.strip() else "unknown"
        accumulator.add(
            model_id=model_id,
            input_tokens=_token_value(usage.get("input_tokens")),
            output_tokens=_token_value(usage.get("output_tokens")),
            cache_read_tokens=_token_value(usage.get("cache_read_input_tokens")),
            cache_creation_tokens=_token_value(
                usage.get("cache_creation_input_tokens")
            ),
        )


def _token_value(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _parse_timestamp(value) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
