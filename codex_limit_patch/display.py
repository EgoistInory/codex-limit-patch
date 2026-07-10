from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .parser import CodexLimitState, ResetBankCredit, countdown_text, format_local_time


def render_pill(state: CodexLimitState, settings: dict[str, Any] | None = None) -> str:
    five = _remaining_percent_text(state.fiveHour.usedPercent if state.fiveHour else None)
    weekly = _remaining_percent_text(state.weekly.usedPercent if state.weekly else None)
    reset = _reset_text(state)
    soon = _expiring_summary(state, settings=settings)
    text = f"Codex 5h {five} | Week {weekly} | {reset}"
    if soon:
        text += f" | {soon}"
    if state.stale:
        text += " | cached"
    return text


def render_expanded(state: CodexLimitState, settings: dict[str, Any] | None = None) -> str:
    lines = [
        f"Plan: {state.planName or 'Unknown'}",
        f"Codex 5h remaining: {_remaining_percent_text(state.fiveHour.usedPercent if state.fiveHour else None)}",
        f"Codex 5h resets at: {_reset_at_text(state.fiveHour.resetsAt if state.fiveHour else None)}",
        f"Weekly remaining: {_remaining_percent_text(state.weekly.usedPercent if state.weekly else None)}",
        f"Weekly resets at: {_reset_at_text(state.weekly.resetsAt if state.weekly else None)}",
    ]
    if state.stale:
        lines.extend(
            [
                "",
                f"Source: {state.sourceLabel or state.dataSource}",
                f"Snapshot: {_snapshot_text(state.lastUpdatedAt)}",
            ]
        )
        if state.errorMessage:
            lines.append(f"Warning: {state.errorMessage}")
    lines.extend(["", "Reset Bank"])
    bank = state.resetBank
    if bank is None:
        lines.extend(
            [
                "Unavailable",
                "This Codex version or account did not provide reset credit data.",
            ]
        )
        return "\n".join(lines)
    if bank.errorMessage:
        lines.append("Unavailable")
        lines.append("This Codex version or account did not provide reset credit data.")
        lines.append(f"Reason: {bank.errorMessage}")
        return "\n".join(lines)
    lines.append(f"Available: {_count_text(bank.availableCount)}")
    if bank.sourceLabel:
        lines.append(f"Source: {bank.sourceLabel}")
    lines.append(f"Snapshot: {_snapshot_text(bank.snapshotAt)}")
    if bank.warningMessage:
        lines.append(f"Warning: {bank.warningMessage}")
    expiry_alert = _expiring_summary(state, settings=settings)
    if expiry_alert:
        lines.append(f"Expiry alert: {expiry_alert}")
    if not bank.detailsAvailable:
        lines.append(bank.detailsMessage or "Reset credit details not available from local safe sources.")
        return "\n".join(lines)
    lines.append("")
    for index, credit in enumerate(bank.credits, start=1):
        lines.extend(_credit_lines(index, credit))
        if index != len(bank.credits):
            lines.append("")
    return "\n".join(lines)


def _credit_lines(index: int, credit: ResetBankCredit) -> list[str]:
    status = credit.status.title()
    source = credit.sourceLabel or "Unknown source"
    lines = [
        f"#{index} {status} | {source}",
        f"Granted: {credit.acquiredTimeText or 'Unknown'}",
        f"Expires: {credit.expiresTimeText or 'Not provided'}",
    ]
    if credit.expiresCountdownText:
        lines.append(credit.expiresCountdownText)
    return lines


def _percent_text(value: int | float | None) -> str:
    if value is None:
        return "?"
    return f"{value}%"


def _remaining_percent_text(used_percent: int | float | None) -> str:
    if used_percent is None:
        return "?"
    return f"{max(0, 100 - used_percent)}%"


def _reset_at_text(value: str | None) -> str:
    if not value:
        return "Unknown"
    return format_local_time(value)


def _reset_text(state: CodexLimitState) -> str:
    bank = state.resetBank
    if bank is None or bank.errorMessage:
        return "Reset ?"
    if bank.availableCount is None:
        return "Reset ?"
    return f"Reset x{bank.availableCount}"


def _count_text(value: int | None) -> str:
    return str(value) if value is not None else "Unknown"


def _snapshot_text(value: str | None) -> str:
    if not value:
        return "Unknown"
    return format_local_time(value)


def _expiring_summary(
    state: CodexLimitState,
    settings: dict[str, Any] | None = None,
) -> str:
    bank = state.resetBank
    if not bank or not bank.credits:
        return ""
    now = datetime.now(timezone.utc)
    reset_settings = (settings or {}).get("resetBank", {})
    warn_hours = _number_or_default(reset_settings.get("warnExpireWithinHours"), 72)
    expiring = []
    for credit in bank.credits:
        if credit.status != "available" or not credit.expiresAt:
            continue
        hours_left = _hours_until(credit.expiresAt, now)
        if hours_left is None or hours_left > warn_hours:
            continue
        text = countdown_text(credit.expiresAt, now=now)
        if text.startswith("expires in "):
            expiring.append(text)
    if len(expiring) == 1:
        return expiring[0].replace("expires", "one expires", 1)
    if len(expiring) > 1:
        return f"{len(expiring)} expiring soon"
    return ""


def _hours_until(iso_value: str, now: datetime) -> float | None:
    try:
        expiry = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (expiry - now).total_seconds() / 3600


def _number_or_default(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default
