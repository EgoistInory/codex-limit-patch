from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .parser import normalize_reset_bank, normalize_timestamp


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


def probe_local_rate_limits(
    *,
    debug: Callable[[str], None] | None = None,
) -> dict[str, Any] | None:
    best: tuple[float, str, dict[str, Any]] | None = None
    files_seen = 0
    for root in _rollout_paths():
        if not root.exists():
            continue
        for file_path in _iter_recent_rollout_files(root):
            files_seen += 1
            if files_seen > MAX_FILES:
                break
            found = _probe_rate_limit_file(file_path)
            if found is not None and (best is None or found[0] > best[0]):
                best = found

    if best is None:
        if debug:
            debug("local rollout probe found no rate limit snapshot")
        return None

    _, captured_at, rate_limits = best
    return {
        "result": {"rateLimits": rate_limits},
        "_codexLimitPatch": {
            "source": "local_rollout",
            "sourceLabel": "local Codex rollout cache",
            "snapshotAt": captured_at,
            "stale": True,
        },
    }


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


def _rollout_paths() -> list[Path]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    return [codex_home / "sessions", codex_home / "archived_sessions"]


def _iter_recent_rollout_files(root: Path):
    candidates: list[tuple[float, Path]] = []
    for file_path in root.rglob("rollout-*.jsonl"):
        if not file_path.is_file():
            continue
        try:
            modified_at = file_path.stat().st_mtime
        except OSError:
            continue
        candidates.append((modified_at, file_path))
    for _, file_path in sorted(candidates, key=lambda item: item[0], reverse=True):
        yield file_path


def _probe_rate_limit_file(
    file_path: Path,
) -> tuple[float, str, dict[str, Any]] | None:
    best: tuple[float, str, dict[str, Any]] | None = None
    try:
        fallback_at = datetime.fromtimestamp(
            file_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if len(line) > MAX_LINE_CHARS:
                    continue
                if '"rate_limits"' not in line and '"rateLimits"' not in line:
                    continue
                payload = _parse_json_candidate(line)
                if payload is None:
                    continue
                if not isinstance(payload, dict) or payload.get("type") != "event_msg":
                    continue
                event_payload = payload.get("payload")
                if not isinstance(event_payload, dict):
                    continue
                raw = event_payload.get("rate_limits", event_payload.get("rateLimits"))
                rate_limits = _normalize_rollout_rate_limits(raw)
                if rate_limits is None:
                    continue
                captured_at = normalize_timestamp(
                    payload.get("timestamp") if isinstance(payload, dict) else None
                ) or fallback_at
                candidate = (_timestamp_sort_value(captured_at), captured_at, rate_limits)
                if best is None or candidate[0] > best[0]:
                    best = candidate
    except (OSError, UnicodeError):
        return None
    return best



def _normalize_rollout_rate_limits(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    primary = _normalize_rollout_window(raw.get("primary"))
    secondary = _normalize_rollout_window(raw.get("secondary"))
    if primary is None and secondary is None:
        return None

    normalized: dict[str, Any] = {}
    if primary is not None:
        normalized["primary"] = primary
    if secondary is not None:
        normalized["secondary"] = secondary
    for source, target in (
        ("plan_type", "planType"),
        ("planType", "planType"),
        ("rate_limit_reached_type", "rateLimitReachedType"),
        ("rateLimitReachedType", "rateLimitReachedType"),
    ):
        if source in raw and target not in normalized:
            normalized[target] = raw[source]
    return normalized


def _normalize_rollout_window(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    normalized: dict[str, Any] = {}
    for target, keys in (
        ("usedPercent", ("used_percent", "usedPercent")),
        ("windowDurationMins", ("window_minutes", "windowDurationMins")),
        ("resetsAt", ("resets_at", "resetsAt")),
    ):
        for key in keys:
            if key in raw:
                normalized[target] = raw[key]
                break
    return normalized or None


def _timestamp_sort_value(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


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
