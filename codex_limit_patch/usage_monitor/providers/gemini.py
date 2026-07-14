from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..gemini_logs import GeminiUsageTotals, scan_gemini_sessions
from ..models import AccountSnapshot, ModelUsage
from .base import ProviderDescriptor, ProviderFetchOutcome, run_provider


GEMINI_DESCRIPTOR = ProviderDescriptor(
    id="google",
    display_name="Google Gemini",
    client_name="Gemini CLI",
    account_kind="local_estimate",
    stale_after_seconds=900,
)


class GeminiLocalLogsStrategy:
    id = "google.gemini-local-logs"
    source_type = "local_logs"
    source_label = "Gemini CLI local sessions"

    def __init__(
        self,
        *,
        config_dir: Optional[Path] = None,
        scanner: Callable[..., GeminiUsageTotals] = scan_gemini_sessions,
    ) -> None:
        self.sessions_root = _sessions_root(config_dir)
        self.scanner = scanner

    def is_available(self) -> bool:
        return self.sessions_root.expanduser().is_dir()

    def fetch(self, now: datetime) -> AccountSnapshot:
        current = _as_utc(now)
        local_now = current.astimezone()
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        totals = self.scanner(
            self.sessions_root,
            start=local_start.astimezone(timezone.utc),
            end=current,
        )
        models = tuple(
            ModelUsage(
                model_id=model.model_id,
                display_name=model.model_id,
                input_tokens=model.input_tokens,
                output_tokens=model.output_tokens,
                cache_read_tokens=model.cached_tokens,
            )
            for model in totals.models
        )
        message = (
            "Local usage only; Gemini subscription limits and reset windows "
            "are not read from OAuth credentials."
        )
        if totals.file_errors:
            message += " Some session files could not be read."
        return AccountSnapshot(
            id="google-gemini-cli",
            provider_id=GEMINI_DESCRIPTOR.id,
            provider_name=GEMINI_DESCRIPTOR.display_name,
            client_name=GEMINI_DESCRIPTOR.client_name,
            account_kind=GEMINI_DESCRIPTOR.account_kind,
            status="available",
            source_type=self.source_type,
            source_label=self.source_label,
            fetched_at=_to_iso(current),
            stale_after_seconds=GEMINI_DESCRIPTOR.stale_after_seconds,
            quotas=(),
            models=models,
            requests_today=totals.requests,
            tokens_today=totals.total_tokens,
            message=message,
        )


def fetch_gemini_outcome(
    config_dir: Optional[Path] = None,
    *,
    now: Optional[datetime] = None,
    scanner: Callable[..., GeminiUsageTotals] = scan_gemini_sessions,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    return run_provider(
        GEMINI_DESCRIPTOR,
        [GeminiLocalLogsStrategy(config_dir=config_dir, scanner=scanner)],
        now=current,
    )


def _sessions_root(config_dir: Optional[Path]) -> Path:
    if config_dir is not None:
        root = config_dir
    else:
        configured = os.environ.get("GEMINI_CLI_HOME")
        root = Path(configured) if configured else Path.home() / ".gemini"
    return root.expanduser() / "tmp"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_iso(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")
