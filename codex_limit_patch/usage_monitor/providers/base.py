from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, Sequence, Tuple

from ..models import AccountSnapshot


@dataclass(frozen=True)
class ProviderDescriptor:
    id: str
    display_name: str
    client_name: Optional[str]
    account_kind: str
    stale_after_seconds: int


@dataclass(frozen=True)
class FetchAttempt:
    strategy_id: str
    source_type: str
    source_label: str
    available: bool
    success: bool
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ProviderFetchOutcome:
    descriptor: ProviderDescriptor
    snapshot: AccountSnapshot
    attempts: Tuple[FetchAttempt, ...]


class FetchStrategy(Protocol):
    id: str
    source_type: str
    source_label: str

    def is_available(self) -> bool:
        ...

    def fetch(self, now: datetime) -> AccountSnapshot:
        ...


def run_provider(
    descriptor: ProviderDescriptor,
    strategies: Sequence[FetchStrategy],
    *,
    now: datetime,
) -> ProviderFetchOutcome:
    attempts = []
    for strategy in strategies:
        try:
            available = bool(strategy.is_available())
        except Exception as exc:
            attempts.append(
                _attempt(strategy, available=False, success=False, error=exc)
            )
            continue
        if not available:
            attempts.append(_attempt(strategy, available=False, success=False))
            continue
        try:
            snapshot = strategy.fetch(now)
            if snapshot.provider_id != descriptor.id:
                raise ValueError(
                    "strategy returned provider %s for %s"
                    % (snapshot.provider_id, descriptor.id)
                )
        except Exception as exc:
            attempts.append(_attempt(strategy, available=True, success=False, error=exc))
            continue
        attempts.append(_attempt(strategy, available=True, success=True))
        return ProviderFetchOutcome(
            descriptor=descriptor,
            snapshot=snapshot,
            attempts=tuple(attempts),
        )

    errors = [attempt.error_message for attempt in attempts if attempt.error_message]
    message = errors[-1] if errors else "No configured usage source is available."
    unavailable = AccountSnapshot(
        id="%s-default" % descriptor.id,
        provider_id=descriptor.id,
        provider_name=descriptor.display_name,
        client_name=descriptor.client_name,
        account_kind=descriptor.account_kind,
        status="unavailable",
        source_type="unavailable",
        source_label="No successful source",
        fetched_at=_to_iso(now),
        stale_after_seconds=descriptor.stale_after_seconds,
        message=message,
    )
    return ProviderFetchOutcome(
        descriptor=descriptor,
        snapshot=unavailable,
        attempts=tuple(attempts),
    )


def sanitize_error(exc: Exception) -> str:
    first_line = str(exc).splitlines()[0].strip() if str(exc) else ""
    text = "%s: %s" % (exc.__class__.__name__, first_line or "request failed")
    text = re.sub(
        r"(?i)\b(bearer)\s+[^\s,;]+",
        r"\1 [redacted]",
        text,
    )
    text = re.sub(
        r"(?i)\b(token|api[_-]?key|authorization|cookie|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        text,
    )
    text = " ".join(text.split())
    if len(text) > 160:
        text = text[:157] + "..."
    return text


def _attempt(
    strategy: FetchStrategy,
    *,
    available: bool,
    success: bool,
    error: Optional[Exception] = None,
) -> FetchAttempt:
    return FetchAttempt(
        strategy_id=strategy.id,
        source_type=strategy.source_type,
        source_label=strategy.source_label,
        available=available,
        success=success,
        error_message=sanitize_error(error) if error else None,
    )


def _to_iso(value: datetime) -> str:
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
