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
) -> MenuPresentation:
    accounts = payload.get("accounts") or []
    live_provider_ids = payload.get("live_provider_ids")
    if isinstance(live_provider_ids, list):
        live_ids = set(live_provider_ids)
        accounts = [account for account in accounts if account.get("provider_id") in live_ids]

    alerts = payload.get("alerts") or []
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
        title = "AI ×"
    elif critical:
        title = "AI !%s" % critical
    elif warning:
        title = "AI •%s" % warning
    else:
        title = "AI ✓"

    rows = tuple(_menu_row(account) for account in accounts)
    return MenuPresentation(
        title=title,
        rows=rows,
        updated_label=_updated_label(payload.get("generated_at")),
        error_message=error_message,
    )


def _menu_row(account: Dict[str, Any]) -> MenuRow:
    status = str(account.get("status") or "unavailable")
    if status == "unavailable":
        detail = "Unavailable"
    else:
        detail = _metric_detail(account)
    return MenuRow(
        provider_id=str(account.get("provider_id") or "unknown"),
        label=str(account.get("provider_name") or "Unknown provider"),
        detail=detail,
        status=status,
        source_label=str(account.get("source_label") or "Unknown source"),
    )


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
    return "Updated %s UTC" % utc.strftime("%Y-%m-%d %H:%M")


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
