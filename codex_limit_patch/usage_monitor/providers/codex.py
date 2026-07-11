from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from ...client import CodexAppServerClient, find_codex_binary
from ...parser import LimitWindow, build_codex_limit_state
from ..models import AccountSnapshot, QuotaWindow
from .base import ProviderDescriptor, ProviderFetchOutcome, run_provider


CODEX_DESCRIPTOR = ProviderDescriptor(
    id="openai",
    display_name="OpenAI",
    client_name="Codex",
    account_kind="subscription",
    stale_after_seconds=300,
)


class CodexAppServerStrategy:
    id = "openai.codex-app-server"
    source_type = "local_client"
    source_label = "Codex app-server"

    def __init__(
        self,
        codex_bin: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.codex_bin = codex_bin
        self.client = client

    def is_available(self) -> bool:
        if self.client is not None:
            return True
        find_codex_binary(self.codex_bin)
        return True

    def fetch(self, now: datetime) -> AccountSnapshot:
        client = self.client or CodexAppServerClient(self.codex_bin)
        response = client.read_rate_limits()
        state = build_codex_limit_state(response, snapshot_at=now, now=now)
        if state.stale and state.errorMessage:
            raise RuntimeError(state.errorMessage)

        quotas: List[QuotaWindow] = []
        primary = _map_window("five-hour", "5-hour window", state.fiveHour)
        secondary = _map_window("weekly", "Weekly window", state.weekly)
        if primary is not None:
            quotas.append(primary)
        if secondary is not None:
            quotas.append(secondary)
        if state.resetBank and state.resetBank.availableCount is not None:
            quotas.append(
                QuotaWindow(
                    id="reset-credits",
                    label="Reset credits",
                    unit="credits",
                    remaining=state.resetBank.availableCount,
                    accuracy="exact",
                )
            )

        return AccountSnapshot(
            id="openai-codex",
            provider_id=CODEX_DESCRIPTOR.id,
            provider_name=CODEX_DESCRIPTOR.display_name,
            client_name=CODEX_DESCRIPTOR.client_name,
            account_kind=CODEX_DESCRIPTOR.account_kind,
            status="available",
            source_type=self.source_type,
            source_label=self.source_label,
            fetched_at=state.lastUpdatedAt or _to_iso(now),
            stale_after_seconds=CODEX_DESCRIPTOR.stale_after_seconds,
            plan_name=state.planName,
            quotas=tuple(quotas),
            message=(
                "A Codex quota window is exhausted."
                if not state.available
                else None
            ),
        )


def fetch_codex_outcome(
    codex_bin: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    client: Optional[Any] = None,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    return run_provider(
        CODEX_DESCRIPTOR,
        [CodexAppServerStrategy(codex_bin=codex_bin, client=client)],
        now=current,
    )


def _map_window(
    quota_id: str,
    label: str,
    window: Optional[LimitWindow],
) -> Optional[QuotaWindow]:
    if window is None:
        return None
    used = window.usedPercent
    remaining = None if used is None else max(0, 100 - used)
    return QuotaWindow(
        id=quota_id,
        label=label,
        unit="percent",
        used=used,
        limit=100 if used is not None else None,
        remaining=remaining,
        remaining_percent=remaining,
        resets_at=window.resetsAt,
        period_label=_duration_label(window.windowDurationMins),
        accuracy="exact",
    )


def _duration_label(minutes: Optional[int]) -> Optional[str]:
    if minutes is None:
        return None
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "%s day%s" % (days, "" if days == 1 else "s")
    if minutes % 60 == 0:
        hours = minutes // 60
        return "%s hour%s" % (hours, "" if hours == 1 else "s")
    return "%s minutes" % minutes


def _to_iso(value: datetime) -> str:
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
