from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..claude_logs import ClaudeUsageTotals, scan_claude_projects
from ..models import AccountSnapshot, ModelUsage
from .base import ProviderDescriptor, ProviderFetchOutcome, run_provider


CLAUDE_DESCRIPTOR = ProviderDescriptor(
    id="anthropic",
    display_name="Anthropic",
    client_name="Claude Code",
    account_kind="local_estimate",
    stale_after_seconds=900,
)


class ClaudeLocalLogsStrategy:
    id = "anthropic.claude-local-logs"
    source_type = "local_logs"
    source_label = "Claude Code local logs"

    def __init__(
        self,
        *,
        config_dir: Optional[Path] = None,
        projects_dir: Optional[Path] = None,
        scanner: Callable[..., ClaudeUsageTotals] = scan_claude_projects,
    ) -> None:
        self.projects_dir = projects_dir or _projects_dir(config_dir)
        self.scanner = scanner

    def is_available(self) -> bool:
        return self.projects_dir.expanduser().is_dir()

    def fetch(self, now: datetime) -> AccountSnapshot:
        current = _as_utc(now)
        local_now = current.astimezone()
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = local_start.astimezone(timezone.utc)
        totals = self.scanner(self.projects_dir, start=start, end=current)
        models = tuple(
            ModelUsage(
                model_id=model.model_id,
                display_name=model.model_id,
                input_tokens=model.input_tokens,
                output_tokens=model.output_tokens,
                cache_read_tokens=model.cache_read_tokens,
                cache_creation_tokens=model.cache_creation_tokens,
            )
            for model in totals.models
        )
        message = (
            "Local usage only; Claude subscription limits and reset windows "
            "are not available from this source."
        )
        if totals.file_errors:
            message += " Some log files could not be read."
        return AccountSnapshot(
            id="anthropic-claude-code",
            provider_id=CLAUDE_DESCRIPTOR.id,
            provider_name=CLAUDE_DESCRIPTOR.display_name,
            client_name=CLAUDE_DESCRIPTOR.client_name,
            account_kind=CLAUDE_DESCRIPTOR.account_kind,
            status="available",
            source_type=self.source_type,
            source_label=self.source_label,
            fetched_at=_to_iso(current),
            stale_after_seconds=CLAUDE_DESCRIPTOR.stale_after_seconds,
            quotas=(),
            models=models,
            requests_today=totals.requests,
            tokens_today=totals.total_tokens,
            message=message,
        )


def fetch_claude_outcome(
    config_dir: Optional[Path] = None,
    *,
    projects_dir: Optional[Path] = None,
    now: Optional[datetime] = None,
    scanner: Callable[..., ClaudeUsageTotals] = scan_claude_projects,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    strategy = ClaudeLocalLogsStrategy(
        config_dir=config_dir,
        projects_dir=projects_dir,
        scanner=scanner,
    )
    return run_provider(CLAUDE_DESCRIPTOR, [strategy], now=current)


def _projects_dir(config_dir: Optional[Path]) -> Path:
    if config_dir is not None:
        root = config_dir
    else:
        configured = os.environ.get("CLAUDE_CONFIG_DIR")
        root = Path(configured) if configured else Path.home() / ".claude"
    return root.expanduser() / "projects"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_iso(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")
