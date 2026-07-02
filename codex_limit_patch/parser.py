from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


ACQUIRED_FIELDS = (
    "acquiredAt",
    "acquired_at",
    "earnedAt",
    "earned_at",
    "grantedAt",
    "granted_at",
    "createdAt",
    "created_at",
    "issuedAt",
    "issued_at",
    "awardedAt",
    "awarded_at",
    "receivedAt",
    "received_at",
)

EXPIRES_FIELDS = (
    "expiresAt",
    "expires_at",
    "expirationAt",
    "expiration_at",
    "expireAt",
    "expire_at",
    "validUntil",
    "valid_until",
    "endsAt",
    "ends_at",
    "deadlineAt",
    "deadline_at",
)

SOURCE_FIELDS = (
    "source",
    "reason",
    "grantType",
    "grant_type",
    "creditType",
    "credit_type",
    "origin",
    "campaign",
    "promotion",
)

DETAIL_ARRAY_FIELDS = (
    "credits",
    "items",
    "entries",
    "resetBank",
    "reset_bank",
)


@dataclass
class LimitWindow:
    usedPercent: int | float | None = None
    windowDurationMins: int | None = None
    resetsAt: str | None = None


@dataclass
class ResetBankCredit:
    id: str | None = None
    status: str = "unknown"
    source: str | None = "unknown"
    sourceLabel: str | None = "Unknown source"
    grantedAt: str | None = None
    earnedAt: str | None = None
    acquiredAt: str | None = None
    expiresAt: str | None = None
    usedAt: str | None = None
    acquiredTimeText: str = "Unknown"
    expiresTimeText: str = "Not provided"
    expiresCountdownText: str = ""
    raw: Any | None = None


@dataclass
class ResetBankState:
    availableCount: int | None = None
    totalCount: int | None = None
    usedCount: int | None = None
    expiredCount: int | None = None
    credits: list[ResetBankCredit] = field(default_factory=list)
    snapshotAt: str | None = None
    detailsAvailable: bool = False
    stale: bool = False
    dataSource: str = "app_server"
    sourceLabel: str | None = None
    detailsMessage: str | None = None
    errorMessage: str | None = None
    warningMessage: str | None = None
    rawShape: Any | None = None


@dataclass
class CodexLimitState:
    available: bool = False
    stale: bool = False
    planName: str | None = None
    fiveHour: LimitWindow | None = None
    weekly: LimitWindow | None = None
    resetCredits: int | None = None
    resetBank: ResetBankState | None = None
    lastUpdatedAt: str | None = None
    errorMessage: str | None = None


def normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp >= 10**12:
            timestamp = timestamp / 1000
        return _timestamp_to_iso(timestamp)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return normalize_timestamp(int(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%a, %d %b %Y %H:%M:%S %Z")
                parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return None


def build_codex_limit_state(
    response: dict[str, Any] | None,
    *,
    snapshot_at: datetime | None = None,
    now: datetime | None = None,
    debug: Callable[[str], None] | None = None,
) -> CodexLimitState:
    snapshot = snapshot_at or datetime.now(timezone.utc)
    current = now or snapshot
    if not isinstance(response, dict):
        return CodexLimitState(
            available=False,
            stale=True,
            lastUpdatedAt=_datetime_to_iso(snapshot),
            errorMessage="Invalid app-server response",
        )

    body = response.get("result", response)
    rate_limits = body.get("rateLimits") if isinstance(body, dict) else None
    if not isinstance(rate_limits, dict):
        rate_limits = {}
    reset_raw = body.get("rateLimitResetCredits") if isinstance(body, dict) else None
    reset_bank = normalize_reset_bank(
        reset_raw,
        snapshot_at=snapshot,
        now=current,
        details_message="Details: not provided by supported Codex app-server",
        debug=debug,
    )
    plan_name = _string_or_none(rate_limits.get("planType")) or _string_or_none(
        rate_limits.get("planName")
    )
    five_hour = _normalize_window(rate_limits.get("primary"))
    weekly = _normalize_window(rate_limits.get("secondary"))
    limit_reached = rate_limits.get("rateLimitReachedType")
    available = not bool(limit_reached)

    return CodexLimitState(
        available=available,
        stale=False,
        planName=plan_name,
        fiveHour=five_hour,
        weekly=weekly,
        resetCredits=reset_bank.availableCount if reset_bank else None,
        resetBank=reset_bank,
        lastUpdatedAt=_datetime_to_iso(snapshot),
    )


def normalize_reset_bank(
    raw: Any,
    *,
    snapshot_at: datetime | None = None,
    now: datetime | None = None,
    data_source: str = "app_server",
    source_label: str | None = None,
    details_message: str | None = None,
    debug: Callable[[str], None] | None = None,
) -> ResetBankState:
    snapshot = snapshot_at or datetime.now(timezone.utc)
    current = now or snapshot
    if raw is None:
        state = ResetBankState(
            snapshotAt=_datetime_to_iso(snapshot),
            detailsAvailable=False,
            stale=False,
            dataSource=data_source,
            sourceLabel=source_label,
            detailsMessage=details_message,
            errorMessage="Reset bank data not provided",
            rawShape=raw_shape(raw),
        )
        _debug_shape(debug, state)
        return state

    if not isinstance(raw, dict):
        state = ResetBankState(
            snapshotAt=_datetime_to_iso(snapshot),
            detailsAvailable=False,
            stale=False,
            dataSource=data_source,
            sourceLabel=source_label,
            detailsMessage=details_message,
            errorMessage="Unsupported reset bank data shape",
            rawShape=raw_shape(raw),
        )
        _debug_shape(debug, state)
        return state

    credits_raw = _find_credit_rows(raw)
    credits = [
        _normalize_credit(row, now=current) for row in credits_raw if isinstance(row, dict)
    ]
    available_count = _first_int(
        raw,
        ("availableCount", "count", "balance", "available_count", "available"),
    )
    total_count = _first_int(raw, ("totalCount", "total", "total_earned_count"))
    used_count = _first_int(raw, ("usedCount", "used"))
    expired_count = _first_int(raw, ("expiredCount", "expired"))

    if available_count is None and credits:
        available_count = sum(1 for credit in credits if credit.status == "available")
    if total_count is None and credits:
        total_count = len(credits)
    if used_count is None and credits:
        used_count = sum(1 for credit in credits if credit.status == "used")
    if expired_count is None and credits:
        expired_count = sum(1 for credit in credits if credit.status == "expired")

    warning = None
    if available_count is not None and credits:
        detail_available = sum(1 for credit in credits if credit.status == "available")
        if available_count != detail_available:
            warning = "Detail count may differ from backend snapshot"

    state = ResetBankState(
        availableCount=available_count,
        totalCount=total_count,
        usedCount=used_count,
        expiredCount=expired_count,
        credits=credits,
        snapshotAt=_datetime_to_iso(snapshot),
        detailsAvailable=bool(credits),
        stale=False,
        dataSource=data_source,
        sourceLabel=source_label,
        detailsMessage=details_message,
        warningMessage=warning,
        rawShape=raw_shape(raw),
    )
    _debug_shape(debug, state)
    return state


def to_plain(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {
            k: to_plain(v)
            for k, v in asdict(obj).items()
            if v is not None and k != "raw"
        }
    if isinstance(obj, list):
        return [to_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items() if v is not None}
    return obj


def format_local_time(iso_value: str | None) -> str:
    if not iso_value:
        return "Unknown"
    parsed = normalize_timestamp(iso_value)
    if not parsed:
        return "Unknown"
    dt = datetime.fromisoformat(parsed.replace("Z", "+00:00")).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M")


def countdown_text(expires_at: str | None, *, now: datetime | None = None) -> str:
    if not expires_at:
        return "no expiry shown"
    parsed = normalize_timestamp(expires_at)
    if not parsed:
        return "no expiry shown"
    current = now or datetime.now(timezone.utc)
    expiry = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
    delta = expiry - current
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = abs(total_seconds)
        days = total_seconds // 86400
        if days >= 1:
            return f"expired {days}d ago"
        hours = total_seconds // 3600
        if hours >= 1:
            return f"expired {hours}h ago"
        minutes = max(1, total_seconds // 60)
        return f"expired {minutes}m ago"
    if total_seconds < 3600:
        minutes = max(1, total_seconds // 60)
        return f"expires in {minutes}m"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"expires in {hours}h {minutes}m"
    days = total_seconds // 86400
    return f"expires in {days}d"


def raw_shape(value: Any, *, depth: int = 0, max_depth: int = 4) -> Any:
    if depth >= max_depth:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): raw_shape(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        return [raw_shape(value[0], depth=depth + 1, max_depth=max_depth)]
    return type(value).__name__


def _normalize_credit(raw: dict[str, Any], *, now: datetime) -> ResetBankCredit:
    acquired_at = _first_timestamp(raw, ACQUIRED_FIELDS)
    expires_at = _first_timestamp(raw, EXPIRES_FIELDS)
    used_at = _first_timestamp(raw, ("usedAt", "redeemedAt", "consumedAt", "spentAt"))
    granted_at = _first_timestamp(raw, ("grantedAt", "granted_at"))
    earned_at = _first_timestamp(raw, ("earnedAt", "earned_at"))
    source_raw = _first_value(raw, SOURCE_FIELDS)
    status = _status_for(raw, expires_at=expires_at, used_at=used_at, now=now)
    source = _source_for(source_raw)
    source_label = _source_label(source_raw)
    return ResetBankCredit(
        id=_string_or_none(_first_value(raw, ("id", "creditId", "resetCreditId"))),
        status=status,
        source=source,
        sourceLabel=source_label,
        grantedAt=granted_at,
        earnedAt=earned_at,
        acquiredAt=acquired_at,
        expiresAt=expires_at,
        usedAt=used_at,
        acquiredTimeText=format_local_time(acquired_at) if acquired_at else "Unknown",
        expiresTimeText=format_local_time(expires_at) if expires_at else "Not provided",
        expiresCountdownText=countdown_text(expires_at, now=now) if expires_at else "",
        raw=raw,
    )


def _find_credit_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for field_name in DETAIL_ARRAY_FIELDS:
        value = raw.get(field_name)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _find_credit_rows(value)
            if nested:
                return nested
    return []


def _status_for(
    raw: dict[str, Any],
    *,
    expires_at: str | None,
    used_at: str | None,
    now: datetime,
) -> str:
    status_raw = _string_or_none(raw.get("status"))
    if status_raw:
        normalized = status_raw.strip().lower()
        if normalized in {"available", "active", "valid"}:
            return "available"
        if normalized in {"used", "redeemed", "consumed", "spent"}:
            return "used"
        if normalized == "expired":
            return "expired"
        return "unknown"
    if used_at:
        return "used"
    if expires_at:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expiry < now:
            return "expired"
    return "unknown"


def _source_for(value: Any) -> str:
    label = _string_or_none(value)
    if not label:
        return "unknown"
    normalized = label.lower()
    if any(term in normalized for term in ("launch", "initial", "free")):
        return "launch_grant"
    if any(term in normalized for term in ("referral", "invite", "friend")):
        return "referral"
    if any(term in normalized for term in ("official", "compensation", "reset", "grant")):
        return "official_grant"
    if any(term in normalized for term in ("manual", "support")):
        return "manual_grant"
    return "unknown"


def _source_label(value: Any) -> str:
    label = _string_or_none(value)
    return label if label else "Unknown source"


def _first_timestamp(raw: dict[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = _case_insensitive_get(raw, name)
        parsed = normalize_timestamp(value)
        if parsed:
            return parsed
    return None


def _normalize_window(raw: Any) -> LimitWindow | None:
    if not isinstance(raw, dict):
        return None
    return LimitWindow(
        usedPercent=raw.get("usedPercent"),
        windowDurationMins=raw.get("windowDurationMins"),
        resetsAt=normalize_timestamp(raw.get("resetsAt")),
    )


def _first_value(raw: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        value = _case_insensitive_get(raw, name)
        if value is not None:
            return value
    return None


def _case_insensitive_get(raw: dict[str, Any], name: str) -> Any:
    if name in raw:
        return raw[name]
    lower_name = name.lower()
    for key, value in raw.items():
        if isinstance(key, str) and key.lower() == lower_name:
            return value
    return None


def _first_int(raw: dict[str, Any], names: tuple[str, ...]) -> int | None:
    value = _first_value(raw, names)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _timestamp_to_iso(timestamp: float) -> str | None:
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _datetime_to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _debug_shape(debug: Callable[[str], None] | None, state: ResetBankState) -> None:
    if not debug:
        return
    details = "yes" if state.detailsAvailable else "no"
    count_only = "yes" if state.availableCount is not None and not state.detailsAvailable else "no"
    field_present = "no" if state.rawShape == "NoneType" else "yes"
    debug(
        "reset_bank "
        f"field_present={field_present} details_available={details} count_only={count_only} "
        f"available_count={state.availableCount} raw_shape={state.rawShape}"
    )
