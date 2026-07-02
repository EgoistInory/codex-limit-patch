from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .parser import normalize_reset_bank


KEYWORDS = (
    "granted_at",
    "grantedAt",
    "expires_at",
    "expiresAt",
    "rateLimitResetCredits",
    "rate-limit-reset-credits",
    "resetBank",
    "availableCount",
    "credits",
)

MAX_LINE_CHARS = 80_000
MAX_FILES = 500


def probe_local_safe_sources(
    *,
    snapshot_at: datetime | None = None,
    now: datetime | None = None,
    debug: Callable[[str], None] | None = None,
) -> Any | None:
    snapshot = snapshot_at or datetime.now(timezone.utc)
    current = now or snapshot
    for path in _allowed_paths():
        if not path.exists():
            continue
        files_seen = 0
        for file_path in _iter_candidate_files(path):
            files_seen += 1
            if files_seen > MAX_FILES:
                break
            found = _probe_file(file_path, snapshot_at=snapshot, now=current, debug=debug)
            if found is not None:
                return found
    if debug:
        debug("local_safe_probe no reset credit details found in allowed paths")
    return None


def _allowed_paths() -> list[Path]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    return [
        codex_home / "sessions",
        codex_home / "archived_sessions",
        codex_home / "logs",
    ]


def _iter_candidate_files(root: Path):
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        yield file_path


def _probe_file(
    file_path: Path,
    *,
    snapshot_at: datetime,
    now: datetime,
    debug: Callable[[str], None] | None,
):
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if len(line) > MAX_LINE_CHARS:
                    continue
                if not any(keyword in line for keyword in KEYWORDS):
                    continue
                payload = _parse_json_candidate(line)
                if payload is None:
                    continue
                raw = _extract_reset_bank(payload)
                if raw is None:
                    continue
                state = normalize_reset_bank(
                    raw,
                    snapshot_at=snapshot_at,
                    now=now,
                    data_source="local_safe_probe",
                    source_label="local safe sources",
                    details_message="Reset credit details discovered in local safe sources.",
                    debug=debug,
                )
                if state.detailsAvailable and _has_granted_and_expires(state):
                    return state
    except (OSError, UnicodeError):
        return None
    return None


def _parse_json_candidate(line: str) -> Any | None:
    text = line.strip().lstrip("\ufeff")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _extract_reset_bank(payload: Any) -> Any | None:
    if isinstance(payload, dict):
        if "rateLimitResetCredits" in payload:
            return payload["rateLimitResetCredits"]
        if "rate_limit_reset_credits" in payload:
            return payload["rate_limit_reset_credits"]
        if "resetBank" in payload:
            return payload["resetBank"]
        if "credits" in payload and (
            "availableCount" in payload or "available_count" in payload
        ):
            return payload
        for value in payload.values():
            found = _extract_reset_bank(value)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _extract_reset_bank(value)
            if found is not None:
                return found
    return None


def _has_granted_and_expires(state: Any) -> bool:
    for credit in state.credits:
        if (credit.grantedAt or credit.earnedAt or credit.acquiredAt) and credit.expiresAt:
            return True
    return False
