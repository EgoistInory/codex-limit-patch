from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from .multi_live_demo import build_multi_live_payload
from .providers.base import ProviderFetchOutcome
from .providers.claude import fetch_claude_outcome
from .providers.codex import fetch_codex_outcome
from .providers.deepseek import fetch_deepseek_outcome


PROVIDER_ORDER = ("openai", "anthropic", "deepseek")


def build_three_source_payload(
    fixture_path: Path,
    *,
    outcomes: Sequence[ProviderFetchOutcome],
    now: datetime,
) -> Dict[str, Any]:
    outcomes_by_id = {outcome.descriptor.id: outcome for outcome in outcomes}
    if len(outcomes_by_id) != len(outcomes):
        raise ValueError("provider outcomes must be unique")
    missing = [provider_id for provider_id in PROVIDER_ORDER if provider_id not in outcomes_by_id]
    if missing:
        raise ValueError("missing provider outcomes: %s" % ", ".join(missing))
    ordered = [outcomes_by_id[provider_id] for provider_id in PROVIDER_ORDER]
    return build_multi_live_payload(fixture_path, outcomes=ordered, now=now)


def collect_three_source_payload(
    fixture_path: Path,
    *,
    codex_bin: Optional[str] = None,
    claude_config_dir: Optional[Path] = None,
    deepseek_api_key: Optional[str] = None,
    deepseek_environ: Optional[Mapping[str, str]] = None,
    now: Optional[datetime] = None,
    codex_fetcher: Callable[..., ProviderFetchOutcome] = fetch_codex_outcome,
    claude_fetcher: Callable[..., ProviderFetchOutcome] = fetch_claude_outcome,
    deepseek_fetcher: Callable[..., ProviderFetchOutcome] = fetch_deepseek_outcome,
) -> Dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    outcomes = [
        codex_fetcher(codex_bin=codex_bin, now=current),
        claude_fetcher(config_dir=claude_config_dir, now=current),
        deepseek_fetcher(
            deepseek_api_key,
            environ=deepseek_environ,
            now=current,
        ),
    ]
    return build_three_source_payload(fixture_path, outcomes=outcomes, now=current)
