from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import AccountSnapshot


SEVERITY_ORDER: Dict[str, int] = {
    "critical": 0,
    "warning": 1,
    "info": 2,
}
CURRENCY_UNITS = {"CNY", "USD", "EUR", "GBP", "JPY"}


@dataclass(frozen=True)
class UsageAlert:
    account_id: str
    kind: str
    severity: str
    title: str
    message: str
    quota_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "account_id": self.account_id,
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "quota_id": self.quota_id,
        }


def quota_severity(remaining_percent: Optional[float]) -> Optional[str]:
    if remaining_percent is None:
        return None
    if remaining_percent <= 10:
        return "critical"
    if remaining_percent <= 20:
        return "warning"
    return None


def evaluate_alerts(
    snapshot: AccountSnapshot,
    *,
    now: datetime,
    low_balance: float = 10.0,
) -> List[UsageAlert]:
    alerts: List[UsageAlert] = []
    if snapshot.status == "unavailable":
        alerts.append(
            UsageAlert(
                account_id=snapshot.id,
                kind="unavailable",
                severity="critical",
                title="%s is unavailable" % snapshot.provider_name,
                message=snapshot.message or "No trustworthy usage snapshot is available.",
            )
        )
    elif snapshot.status == "degraded":
        alerts.append(
            UsageAlert(
                account_id=snapshot.id,
                kind="availability",
                severity="warning",
                title="%s availability is degraded" % snapshot.provider_name,
                message=snapshot.message or "The provider reports limited availability.",
            )
        )

    for quota in snapshot.quotas:
        severity = quota_severity(_as_float(quota.remaining_percent))
        if severity:
            alerts.append(
                UsageAlert(
                    account_id=snapshot.id,
                    quota_id=quota.id,
                    kind="quota",
                    severity=severity,
                    title="%s quota is low" % snapshot.provider_name,
                    message="%s has %s%% remaining."
                    % (quota.label, _format_number(quota.remaining_percent)),
                )
            )
        if (
            quota.unit.upper() in CURRENCY_UNITS
            and quota.remaining is not None
            and float(quota.remaining) <= low_balance
        ):
            alerts.append(
                UsageAlert(
                    account_id=snapshot.id,
                    quota_id=quota.id,
                    kind="balance",
                    severity="warning",
                    title="%s balance is low" % snapshot.provider_name,
                    message="%s %s remaining."
                    % (_format_number(quota.remaining), quota.unit.upper()),
                )
            )

    stale_message = _stale_message(snapshot, now=now)
    if stale_message:
        alerts.append(
            UsageAlert(
                account_id=snapshot.id,
                kind="stale",
                severity="warning",
                title="%s data is stale" % snapshot.provider_name,
                message=stale_message,
            )
        )

    return sorted(
        alerts,
        key=lambda alert: (
            SEVERITY_ORDER.get(alert.severity, 99),
            alert.kind,
            alert.quota_id or "",
        ),
    )


def _stale_message(snapshot: AccountSnapshot, *, now: datetime) -> Optional[str]:
    fetched_at = _parse_time(snapshot.fetched_at)
    if fetched_at is None:
        return "The source returned an invalid refresh timestamp."
    current = now
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_seconds = (current.astimezone(timezone.utc) - fetched_at).total_seconds()
    if age_seconds <= snapshot.stale_after_seconds:
        return None
    return "Last successful refresh was %s minutes ago." % max(1, int(age_seconds // 60))


def _parse_time(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _format_number(value) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return ("%.2f" % number).rstrip("0").rstrip(".")
