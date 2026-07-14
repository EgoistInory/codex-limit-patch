from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from .multi_live_demo import build_multi_live_payload
from .providers.base import ProviderFetchOutcome
from .providers.claude import fetch_claude_outcome
from .providers.codex import fetch_codex_outcome
from .providers.deepseek import fetch_deepseek_outcome
from .providers.gemini import fetch_gemini_outcome
from .providers.kimi import fetch_kimi_outcome
from .providers.minimax import fetch_minimax_outcome
from .providers.zhipu import fetch_zhipu_outcome


PROVIDER_ORDER = ("openai", "anthropic", "deepseek")
SUPPORTED_PROVIDER_ORDER = (
    "openai",
    "anthropic",
    "google",
    "deepseek",
    "kimi",
    "zhipu",
    "minimax",
)


def _build_payload(
    fixture_path: Path,
    *,
    outcomes: Sequence[ProviderFetchOutcome],
    provider_order: Sequence[str],
    now: datetime,
) -> Dict[str, Any]:
    outcomes_by_id = {outcome.descriptor.id: outcome for outcome in outcomes}
    if len(outcomes_by_id) != len(outcomes):
        raise ValueError("provider outcomes must be unique")
    missing = [
        provider_id
        for provider_id in provider_order
        if provider_id not in outcomes_by_id
    ]
    if missing:
        raise ValueError("missing provider outcomes: %s" % ", ".join(missing))
    ordered = [outcomes_by_id[provider_id] for provider_id in provider_order]
    payload = build_multi_live_payload(fixture_path, outcomes=ordered, now=now)
    rank = {provider_id: index for index, provider_id in enumerate(provider_order)}
    accounts = list(enumerate(payload["accounts"]))
    accounts.sort(
        key=lambda item: (
            0,
            rank[item[1]["provider_id"]],
        )
        if item[1]["provider_id"] in rank
        else (1, item[0])
    )
    payload["accounts"] = [account for _index, account in accounts]
    return payload


def build_three_source_payload(
    fixture_path: Path,
    *,
    outcomes: Sequence[ProviderFetchOutcome],
    now: datetime,
) -> Dict[str, Any]:
    return _build_payload(
        fixture_path,
        outcomes=outcomes,
        provider_order=PROVIDER_ORDER,
        now=now,
    )


def build_supported_payload(
    fixture_path: Path,
    *,
    outcomes: Sequence[ProviderFetchOutcome],
    now: datetime,
) -> Dict[str, Any]:
    return _build_payload(
        fixture_path,
        outcomes=outcomes,
        provider_order=SUPPORTED_PROVIDER_ORDER,
        now=now,
    )


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


def collect_supported_payload(
    fixture_path: Path,
    *,
    codex_bin: Optional[str] = None,
    claude_config_dir: Optional[Path] = None,
    gemini_config_dir: Optional[Path] = None,
    deepseek_api_key: Optional[str] = None,
    kimi_api_key: Optional[str] = None,
    zhipu_api_key: Optional[str] = None,
    minimax_api_key: Optional[str] = None,
    api_environ: Optional[Mapping[str, str]] = None,
    deepseek_environ: Optional[Mapping[str, str]] = None,
    kimi_environ: Optional[Mapping[str, str]] = None,
    zhipu_environ: Optional[Mapping[str, str]] = None,
    minimax_environ: Optional[Mapping[str, str]] = None,
    now: Optional[datetime] = None,
    codex_fetcher: Callable[..., ProviderFetchOutcome] = fetch_codex_outcome,
    claude_fetcher: Callable[..., ProviderFetchOutcome] = fetch_claude_outcome,
    gemini_fetcher: Callable[..., ProviderFetchOutcome] = fetch_gemini_outcome,
    deepseek_fetcher: Callable[..., ProviderFetchOutcome] = fetch_deepseek_outcome,
    kimi_fetcher: Callable[..., ProviderFetchOutcome] = fetch_kimi_outcome,
    zhipu_fetcher: Callable[..., ProviderFetchOutcome] = fetch_zhipu_outcome,
    minimax_fetcher: Callable[..., ProviderFetchOutcome] = fetch_minimax_outcome,
) -> Dict[str, Any]:
    current = now or datetime.now(timezone.utc)

    def provider_environ(
        value: Optional[Mapping[str, str]],
    ) -> Optional[Mapping[str, str]]:
        return value if value is not None else api_environ

    outcomes = [
        codex_fetcher(codex_bin=codex_bin, now=current),
        claude_fetcher(config_dir=claude_config_dir, now=current),
        gemini_fetcher(config_dir=gemini_config_dir, now=current),
        deepseek_fetcher(
            deepseek_api_key,
            environ=provider_environ(deepseek_environ),
            now=current,
        ),
        kimi_fetcher(
            kimi_api_key,
            environ=provider_environ(kimi_environ),
            now=current,
        ),
        zhipu_fetcher(
            zhipu_api_key,
            environ=provider_environ(zhipu_environ),
            now=current,
        ),
        minimax_fetcher(
            minimax_api_key,
            environ=provider_environ(minimax_environ),
            now=current,
        ),
    ]
    return build_supported_payload(fixture_path, outcomes=outcomes, now=current)
