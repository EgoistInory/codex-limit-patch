from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class GeminiModelTotals:
    model_id: str
    requests: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    thoughts_tokens: int
    tool_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class GeminiUsageTotals:
    requests: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    thoughts_tokens: int
    tool_tokens: int
    total_tokens: int
    models: Tuple[GeminiModelTotals, ...]
    files_scanned: int = 0
    malformed_lines: int = 0
    ignored_lines: int = 0
    file_errors: int = 0


class _Accumulator:
    def __init__(self) -> None:
        self.seen_ids: Set[str] = set()
        self.requests = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0
        self.thoughts_tokens = 0
        self.tool_tokens = 0
        self.total_tokens = 0
        self.models: Dict[str, Dict[str, int]] = {}
        self.files_scanned = 0
        self.malformed_lines = 0
        self.ignored_lines = 0
        self.file_errors = 0

    def add(self, model_id: str, tokens: Dict[str, int]) -> None:
        self.requests += 1
        for name in (
            "input",
            "output",
            "cached",
            "thoughts",
            "tool",
            "total",
        ):
            target = "%s_tokens" % name
            setattr(self, target, getattr(self, target) + tokens[name])
        model = self.models.setdefault(
            model_id,
            {
                "requests": 0,
                "input": 0,
                "output": 0,
                "cached": 0,
                "thoughts": 0,
                "tool": 0,
                "total": 0,
            },
        )
        model["requests"] += 1
        for name, value in tokens.items():
            model[name] += value

    def freeze(self) -> GeminiUsageTotals:
        models = tuple(
            sorted(
                (
                    GeminiModelTotals(
                        model_id=model_id,
                        requests=values["requests"],
                        input_tokens=values["input"],
                        output_tokens=values["output"],
                        cached_tokens=values["cached"],
                        thoughts_tokens=values["thoughts"],
                        tool_tokens=values["tool"],
                        total_tokens=values["total"],
                    )
                    for model_id, values in self.models.items()
                ),
                key=lambda item: (-item.total_tokens, item.model_id),
            )
        )
        return GeminiUsageTotals(
            requests=self.requests,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cached_tokens=self.cached_tokens,
            thoughts_tokens=self.thoughts_tokens,
            tool_tokens=self.tool_tokens,
            total_tokens=self.total_tokens,
            models=models,
            files_scanned=self.files_scanned,
            malformed_lines=self.malformed_lines,
            ignored_lines=self.ignored_lines,
            file_errors=self.file_errors,
        )


def parse_gemini_log_lines(
    lines: Iterable[str],
    *,
    start: datetime,
    end: datetime,
    accumulator: Optional[_Accumulator] = None,
) -> GeminiUsageTotals:
    current = accumulator or _Accumulator()
    _consume_lines(current, lines, start=_as_utc(start), end=_as_utc(end))
    return current.freeze()


def scan_gemini_sessions(
    root: Path,
    *,
    start: datetime,
    end: datetime,
) -> GeminiUsageTotals:
    sessions_root = root.expanduser().resolve()
    if not sessions_root.is_dir():
        raise FileNotFoundError("Gemini CLI session directory is not available")
    period_start = _as_utc(start)
    period_end = _as_utc(end)
    accumulator = _Accumulator()
    candidates = set(sessions_root.rglob("session-*.jsonl"))
    candidates.update(sessions_root.rglob("session-*.json"))
    for candidate in sorted(candidates):
        if candidate.is_symlink():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            if resolved.parent != sessions_root and sessions_root not in resolved.parents:
                continue
            if resolved.stat().st_mtime < period_start.timestamp():
                continue
            with resolved.open("r", encoding="utf-8", errors="replace") as handle:
                if resolved.suffix == ".json":
                    payload = json.load(handle)
                    messages = payload.get("messages") if isinstance(payload, dict) else None
                    if not isinstance(messages, list):
                        raise ValueError("legacy Gemini session has no messages list")
                    lines = (json.dumps(message) for message in messages)
                    _consume_lines(
                        accumulator,
                        lines,
                        start=period_start,
                        end=period_end,
                    )
                else:
                    _consume_lines(
                        accumulator,
                        handle,
                        start=period_start,
                        end=period_end,
                    )
            accumulator.files_scanned += 1
        except (OSError, ValueError, json.JSONDecodeError):
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
        if not isinstance(row, dict) or row.get("type") != "gemini":
            accumulator.ignored_lines += 1
            continue
        timestamp = _parse_timestamp(row.get("timestamp"))
        tokens_raw = row.get("tokens")
        if timestamp is None or not isinstance(tokens_raw, dict):
            accumulator.ignored_lines += 1
            continue
        if timestamp < start or timestamp >= end:
            accumulator.ignored_lines += 1
            continue
        message_id = row.get("id")
        if isinstance(message_id, str) and message_id:
            if message_id in accumulator.seen_ids:
                accumulator.ignored_lines += 1
                continue
            accumulator.seen_ids.add(message_id)
        model = row.get("model")
        model_id = model.strip() if isinstance(model, str) and model.strip() else "unknown"
        tokens = {
            name: _token_value(tokens_raw.get(name))
            for name in ("input", "output", "cached", "thoughts", "tool", "total")
        }
        if tokens["total"] == 0:
            tokens["total"] = sum(tokens[name] for name in tokens if name != "total")
        accumulator.add(model_id, tokens)


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
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
