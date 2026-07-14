from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class MenuRow:
    provider_id: str
    label: str
    detail: str
    status: str
    source_label: str
    reset_detail: str


@dataclass(frozen=True)
class MenuPresentation:
    title: str
    rows: Tuple[MenuRow, ...]
    updated_label: str
    error_message: Optional[str] = None


def build_menu_presentation(
    payload: Dict[str, Any],
    *,
    error_message: Optional[str] = None,
    now: Optional[datetime] = None,
) -> MenuPresentation:
    current = _utc_datetime(now or datetime.now(timezone.utc))
    accounts = payload.get("accounts") or []
    live_provider_ids = payload.get("live_provider_ids")
    if isinstance(live_provider_ids, list):
        live_ids = set(live_provider_ids)
        accounts = [account for account in accounts if account.get("provider_id") in live_ids]

    unconfigured_provider_ids = _unconfigured_provider_ids(payload)
    unconfigured_account_ids = {
        account.get("id")
        for account in accounts
        if account.get("provider_id") in unconfigured_provider_ids
    }
    alerts = [
        alert
        for alert in (payload.get("alerts") or [])
        if not (
            alert.get("kind") == "unavailable"
            and alert.get("account_id") in unconfigured_account_ids
        )
    ]
    if isinstance(live_provider_ids, list):
        live_account_ids = {account.get("id") for account in accounts}
        alerts = [
            alert
            for alert in alerts
            if not alert.get("account_id") or alert.get("account_id") in live_account_ids
        ]
    critical = sum(1 for alert in alerts if alert.get("severity") == "critical")
    warning = sum(1 for alert in alerts if alert.get("severity") == "warning")
    if error_message:
        title = "AI · Offline"
    elif critical:
        title = "AI · %s %s" % (critical, "alert" if critical == 1 else "alerts")
    elif warning:
        title = "AI · %s %s" % (
            warning,
            "warning" if warning == 1 else "warnings",
        )
    else:
        title = "AI · OK"

    rows = tuple(
        _menu_row(
            account,
            now=current,
            configured=account.get("provider_id") not in unconfigured_provider_ids,
        )
        for account in accounts
    )
    return MenuPresentation(
        title=title,
        rows=rows,
        updated_label=_updated_label(payload.get("generated_at")),
        error_message=error_message,
    )


def _menu_row(account: Dict[str, Any], *, now: datetime, configured: bool) -> MenuRow:
    status = str(account.get("status") or "unavailable")
    if not configured:
        status = "not_configured"
        detail = "Not configured"
    elif status == "unavailable":
        detail = "Unavailable"
    else:
        detail = _metric_detail(account)
    return MenuRow(
        provider_id=str(account.get("provider_id") or "unknown"),
        label=str(account.get("provider_name") or "Unknown provider"),
        detail=detail,
        status=status,
        source_label=str(account.get("source_label") or "Unknown source"),
        reset_detail=_reset_detail(account, now=now),
    )


def _unconfigured_provider_ids(payload: Dict[str, Any]) -> set:
    result = set()
    attempts_by_provider = payload.get("fetch_attempts")
    if not isinstance(attempts_by_provider, dict):
        return result
    for provider_id, attempts in attempts_by_provider.items():
        if not isinstance(attempts, list) or not attempts:
            continue
        if all(attempt.get("available") is False for attempt in attempts):
            result.add(provider_id)
    return result


def _metric_detail(account: Dict[str, Any]) -> str:
    quotas = account.get("quotas") or []
    percentage_parts = []
    for quota in quotas:
        percent = quota.get("remaining_percent")
        if percent is None:
            continue
        percentage_parts.append(
            "%s %s%%" % (quota.get("label") or "Quota", _number(percent))
        )
        if len(percentage_parts) == 2:
            break
    if percentage_parts:
        return " · ".join(percentage_parts)

    tokens = account.get("tokens_today")
    if tokens is not None:
        return "%s tokens today" % _compact_number(tokens)

    for quota in quotas:
        remaining = quota.get("remaining")
        if remaining is None:
            continue
        return "%s %s" % (_number(remaining), quota.get("unit") or "units")

    requests = account.get("requests_today")
    if requests is not None:
        return "%s requests today" % _compact_number(requests)
    return "No metrics reported"


def _updated_label(value: Any) -> str:
    if not isinstance(value, str):
        return "Update time unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Update time unknown"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    utc = parsed.astimezone(timezone.utc)
    return "Data refreshed · %s UTC" % utc.strftime("%Y-%m-%d %H:%M")


def _reset_detail(account: Dict[str, Any], *, now: datetime) -> str:
    parts = []
    for quota in account.get("quotas") or []:
        resets_at = _parse_datetime(quota.get("resets_at"))
        if resets_at is None:
            continue
        parts.append(
            "%s %s"
            % (quota.get("label") or "Quota", _countdown(resets_at, now=now))
        )
        if len(parts) == 2:
            break
    return " · ".join(parts) if parts else "Not reported"


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _countdown(resets_at: datetime, *, now: datetime) -> str:
    seconds = max(0, int((resets_at - now).total_seconds()))
    minutes = seconds // 60
    if minutes <= 0:
        return "due now"
    if minutes < 60:
        return "in %sm" % minutes
    hours = minutes // 60
    if hours < 24:
        remainder = minutes % 60
        return "in %sh%s" % (hours, " %sm" % remainder if remainder else "")
    days = hours // 24
    remainder = hours % 24
    return "in %sd%s" % (days, " %sh" % remainder if remainder else "")


def _compact_number(value: Any) -> str:
    number = float(value)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= threshold:
            return "%s%s" % (_number(number / threshold), suffix)
    return _number(number)


def _number(value: Any) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return ("%.1f" % number).rstrip("0").rstrip(".")
