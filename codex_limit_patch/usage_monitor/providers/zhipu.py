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


ZHIPU_QUOTA_URL = "https://open.bigmodel.cn/api/monitor/usage/quota/limit"
MAX_RESPONSE_BYTES = 1024 * 1024
ZHIPU_DESCRIPTOR = ProviderDescriptor(
    id="zhipu",
    display_name="Zhipu GLM",
    client_name="GLM Coding Plan",
    account_kind="subscription",
    stale_after_seconds=900,
)


class ZhipuQuotaClient:
    def __init__(
        self,
        *,
        endpoint: str = ZHIPU_QUOTA_URL,
        timeout_sec: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "open.bigmodel.cn"
            or parsed.path != "/api/monitor/usage/quota/limit"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Zhipu quota endpoint must use the official HTTPS URL")
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.max_response_bytes = max_response_bytes
        self.opener = opener

    def fetch(self, api_key: str) -> Dict[str, Any]:
        key = api_key.strip()
        if not key:
            raise ValueError("Zhipu API key is required")
        request = Request(
            self.endpoint,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer %s" % key,
                "User-Agent": "codex-limit-patch/0.1",
            },
            method="GET",
        )
        try:
            with self.opener(request, timeout=self.timeout_sec) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise RuntimeError("Zhipu quota API returned HTTP %s" % exc.code) from None
        except (URLError, OSError):
            raise RuntimeError("Zhipu quota API request failed") from None
        if len(raw) > self.max_response_bytes:
            raise RuntimeError("Zhipu quota API response is too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("Zhipu quota API returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Zhipu quota API returned an invalid object")
        return payload


class ZhipuQuotaStrategy:
    id = "zhipu.coding-plan-quota-api"
    source_type = "official_api"
    source_label = "Zhipu Coding Plan quota API"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.explicit_api_key = api_key
        self.client = client or ZhipuQuotaClient()
        self.environ = os.environ if environ is None else environ

    def is_available(self) -> bool:
        return bool(self._api_key())

    def fetch(self, now: datetime) -> AccountSnapshot:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError("Zhipu API key is not configured")
        return parse_zhipu_quota(self.client.fetch(api_key), now=now)

    def _api_key(self) -> Optional[str]:
        for candidate in (
            self.explicit_api_key,
            self.environ.get("ZHIPU_API_KEY"),
            self.environ.get("Z_AI_API_KEY"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None


def parse_zhipu_quota(payload: Dict[str, Any], *, now: datetime) -> AccountSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("Zhipu quota payload must be an object")
    if payload.get("success") is False or payload.get("code") not in (None, 200):
        raise ValueError("Zhipu quota API reported failure")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("data must be an object")
    raw_limits = data.get("limits")
    if not isinstance(raw_limits, list) or not raw_limits:
        raise ValueError("limits must be a non-empty list")
    token_quotas = []
    time_quotas = []
    for index, row in enumerate(raw_limits):
        if not isinstance(row, dict):
            raise ValueError("limits entries must be objects")
        limit_type = row.get("type")
        if limit_type not in ("TOKENS_LIMIT", "TIME_LIMIT"):
            continue
        duration = _duration_minutes(row.get("number"), row.get("unit"))
        quota = _quota_from_limit(row, index=index, duration=duration)
        if limit_type == "TOKENS_LIMIT":
            token_quotas.append((duration or 10**12, quota))
        else:
            time_quotas.append(quota)
    token_quotas.sort(key=lambda item: item[0])
    quotas = [quota for _duration, quota in token_quotas] + time_quotas
    if not quotas:
        raise ValueError("Zhipu quota payload has no supported limits")
    plan_name = _first_text(
        data.get("planName"),
        data.get("plan"),
        data.get("plan_type"),
        data.get("packageName"),
        data.get("level"),
    )
    return AccountSnapshot(
        id="zhipu-coding-plan",
        provider_id=ZHIPU_DESCRIPTOR.id,
        provider_name=ZHIPU_DESCRIPTOR.display_name,
        client_name=ZHIPU_DESCRIPTOR.client_name,
        account_kind=ZHIPU_DESCRIPTOR.account_kind,
        status="available",
        source_type="official_api",
        source_label="Zhipu Coding Plan quota API",
        fetched_at=_to_iso(now),
        stale_after_seconds=ZHIPU_DESCRIPTOR.stale_after_seconds,
        plan_name=plan_name,
        quotas=tuple(quotas),
    )


def fetch_zhipu_outcome(
    api_key: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    client: Optional[Any] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    return run_provider(
        ZHIPU_DESCRIPTOR,
        [ZhipuQuotaStrategy(api_key=api_key, client=client, environ=environ)],
        now=current,
    )


def _quota_from_limit(
    row: Dict[str, Any],
    *,
    index: int,
    duration: Optional[int],
) -> QuotaWindow:
    limit_type = row["type"]
    limit = _optional_number(row.get("usage"))
    remaining = _optional_number(row.get("remaining"))
    current = _optional_number(row.get("currentValue"))
    used = current
    if limit is not None and remaining is not None:
        from_remaining = max(0.0, limit - remaining)
        used = max(from_remaining, current or 0.0)
    reported_used_percent = _optional_number(row.get("percentage"))
    if limit and used is not None:
        used_percent = min(100.0, max(0.0, used / limit * 100))
    else:
        used_percent = reported_used_percent
    remaining_percent = (
        None if used_percent is None else min(100.0, max(0.0, 100 - used_percent))
    )
    if limit_type == "TIME_LIMIT":
        label = "MCP/time quota"
        unit = "calls"
    else:
        label = "%s token quota" % _duration_label(duration)
        unit = "tokens"
    return QuotaWindow(
        id="zhipu-%s-%s" % (limit_type.lower(), index),
        label=label,
        unit=unit,
        used=_clean_number(used),
        limit=_clean_number(limit),
        remaining=_clean_number(remaining),
        remaining_percent=_clean_number(remaining_percent),
        resets_at=normalize_timestamp(row.get("nextResetTime")),
        period_label=("Monthly" if limit_type == "TIME_LIMIT" else _duration_label(duration)),
        accuracy="exact",
    )


def _duration_minutes(number_raw: Any, unit_raw: Any) -> Optional[int]:
    number = _optional_number(number_raw)
    if number is None or not float(number).is_integer() or number <= 0:
        return None
    multipliers = {5: 1, 3: 60, 1: 1440, 6: 10080}
    multiplier = multipliers.get(unit_raw)
    return int(number) * multiplier if multiplier else None


def _duration_label(minutes: Optional[int]) -> str:
    if minutes == 300:
        return "5-hour"
    if minutes == 10080:
        return "Weekly"
    if minutes and minutes % 1440 == 0:
        return "%s-day" % (minutes // 1440)
    if minutes and minutes % 60 == 0:
        return "%s-hour" % (minutes // 60)
    if minutes:
        return "%s-minute" % minutes
    return "Token"


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
