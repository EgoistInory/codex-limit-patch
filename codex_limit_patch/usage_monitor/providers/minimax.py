from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ...parser import normalize_timestamp
from ..models import AccountSnapshot, QuotaWindow
from .base import ProviderDescriptor, ProviderFetchOutcome, run_provider


MINIMAX_QUOTA_URL = "https://www.minimax.io/v1/token_plan/remains"
MAX_RESPONSE_BYTES = 1024 * 1024
MINIMAX_DESCRIPTOR = ProviderDescriptor(
    id="minimax",
    display_name="MiniMax",
    client_name="MiniMax Token Plan",
    account_kind="subscription",
    stale_after_seconds=900,
)


class MiniMaxQuotaClient:
    def __init__(
        self,
        *,
        endpoint: str = MINIMAX_QUOTA_URL,
        timeout_sec: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.minimax.io"
            or parsed.path != "/v1/token_plan/remains"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("MiniMax quota endpoint must use the official HTTPS URL")
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.max_response_bytes = max_response_bytes
        self.opener = opener

    def fetch(self, api_key: str) -> Dict[str, Any]:
        key = api_key.strip()
        if not key:
            raise ValueError("MiniMax API key is required")
        request = Request(
            self.endpoint,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer %s" % key,
                "User-Agent": "codex-limit-patch/0.1",
            },
            method="GET",
        )
        try:
            with self.opener(request, timeout=self.timeout_sec) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise RuntimeError("MiniMax quota API returned HTTP %s" % exc.code) from None
        except (URLError, OSError):
            raise RuntimeError("MiniMax quota API request failed") from None
        if len(raw) > self.max_response_bytes:
            raise RuntimeError("MiniMax quota API response is too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("MiniMax quota API returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("MiniMax quota API returned an invalid object")
        return payload


class MiniMaxQuotaStrategy:
    id = "minimax.token-plan-quota-api"
    source_type = "official_api"
    source_label = "MiniMax Token Plan API"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.explicit_api_key = api_key
        self.client = client or MiniMaxQuotaClient()
        self.environ = os.environ if environ is None else environ

    def is_available(self) -> bool:
        return bool(self._api_key())

    def fetch(self, now: datetime) -> AccountSnapshot:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError("MiniMax API key is not configured")
        return parse_minimax_quota(self.client.fetch(api_key), now=now)

    def _api_key(self) -> Optional[str]:
        for candidate in (
            self.explicit_api_key,
            self.environ.get("MINIMAX_CODING_API_KEY"),
            self.environ.get("MINIMAX_API_KEY"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None


def parse_minimax_quota(payload: Dict[str, Any], *, now: datetime) -> AccountSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("MiniMax quota payload must be an object")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    base_response = payload.get("base_resp")
    if not isinstance(base_response, dict):
        base_response = data.get("base_resp") if isinstance(data, dict) else None
    if isinstance(base_response, dict):
        status = _optional_number(base_response.get("status_code"))
        if status not in (None, 0):
            raise ValueError("MiniMax quota API reported failure")
    rows = data.get("model_remains") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("model_remains must be a non-empty list")
    candidates = [row for row in rows if isinstance(row, dict)]
    general = next(
        (
            row
            for row in candidates
            if str(row.get("model_name") or "").strip().lower() == "general"
        ),
        candidates[0] if candidates else None,
    )
    if general is None:
        raise ValueError("model_remains has no usable entries")
    quotas = [
        _quota_from_lane(
            general,
            weekly=False,
            quota_id="five-hour-tokens",
            label="5-hour token quota",
            period_label="5 hours",
        )
    ]
    weekly_status = _optional_number(general.get("current_weekly_status"))
    has_weekly = any(
        general.get(name) is not None
        for name in (
            "current_weekly_remaining_percent",
            "current_weekly_total_count",
            "current_weekly_usage_count",
        )
    )
    if has_weekly and weekly_status != 3:
        quotas.append(
            _quota_from_lane(
                general,
                weekly=True,
                quota_id="weekly-tokens",
                label="Weekly token quota",
                period_label="7 days",
            )
        )
    plan_name = _first_text(
        data.get("current_subscribe_title"),
        data.get("plan_name"),
        data.get("combo_title"),
        data.get("current_plan_title"),
    )
    return AccountSnapshot(
        id="minimax-token-plan",
        provider_id=MINIMAX_DESCRIPTOR.id,
        provider_name=MINIMAX_DESCRIPTOR.display_name,
        client_name=MINIMAX_DESCRIPTOR.client_name,
        account_kind=MINIMAX_DESCRIPTOR.account_kind,
        status="available",
        source_type="official_api",
        source_label="MiniMax Token Plan API",
        fetched_at=_to_iso(now),
        stale_after_seconds=MINIMAX_DESCRIPTOR.stale_after_seconds,
        plan_name=plan_name,
        quotas=tuple(quotas),
    )


def fetch_minimax_outcome(
    api_key: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    client: Optional[Any] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    return run_provider(
        MINIMAX_DESCRIPTOR,
        [MiniMaxQuotaStrategy(api_key=api_key, client=client, environ=environ)],
        now=current,
    )


def _quota_from_lane(
    row: Dict[str, Any],
    *,
    weekly: bool,
    quota_id: str,
    label: str,
    period_label: str,
) -> QuotaWindow:
    prefix = "current_weekly" if weekly else "current_interval"
    total = _optional_number(row.get("%s_total_count" % prefix))
    remaining = _optional_number(row.get("%s_usage_count" % prefix))
    remaining_percent = _optional_number(row.get("%s_remaining_percent" % prefix))
    used = None
    if total is not None and remaining is not None:
        used = max(0.0, total - remaining)
        if total > 0 and remaining_percent is None:
            remaining_percent = min(100.0, max(0.0, remaining / total * 100))
    if remaining_percent is None and total in (None, 0) and remaining in (None, 0):
        raise ValueError("MiniMax quota lane has no usable values")
    reset_key = "weekly_end_time" if weekly else "end_time"
    return QuotaWindow(
        id=quota_id,
        label=label,
        unit="tokens",
        used=_clean_number(used),
        limit=_clean_number(total),
        remaining=_clean_number(remaining),
        remaining_percent=_clean_number(remaining_percent),
        resets_at=normalize_timestamp(row.get(reset_key)),
        period_label=period_label,
        accuracy="exact",
    )


def _optional_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number >= 0 else None


def _clean_number(value: Optional[float]):
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _to_iso(value: datetime) -> str:
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
