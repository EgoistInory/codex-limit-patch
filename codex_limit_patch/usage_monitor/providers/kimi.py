from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ...parser import normalize_timestamp
from ..models import AccountSnapshot, QuotaWindow
from .base import ProviderDescriptor, ProviderFetchOutcome, run_provider


KIMI_USAGE_URL = "https://api.kimi.com/coding/v1/usages"
MAX_RESPONSE_BYTES = 1024 * 1024
KIMI_DESCRIPTOR = ProviderDescriptor(
    id="kimi",
    display_name="Kimi",
    client_name="Kimi Code",
    account_kind="subscription",
    stale_after_seconds=900,
)


class KimiUsageClient:
    def __init__(
        self,
        *,
        endpoint: str = KIMI_USAGE_URL,
        timeout_sec: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.kimi.com"
            or parsed.path != "/coding/v1/usages"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Kimi usage endpoint must use the official HTTPS URL")
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.max_response_bytes = max_response_bytes
        self.opener = opener

    def fetch(self, api_key: str) -> Dict[str, Any]:
        key = api_key.strip()
        if not key:
            raise ValueError("Kimi API key is required")
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
            raise RuntimeError("Kimi usage API returned HTTP %s" % exc.code) from None
        except (URLError, OSError):
            raise RuntimeError("Kimi usage API request failed") from None
        if len(raw) > self.max_response_bytes:
            raise RuntimeError("Kimi usage API response is too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("Kimi usage API returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Kimi usage API returned an invalid object")
        return payload


class KimiUsageStrategy:
    id = "kimi.coding-usage-api"
    source_type = "official_api"
    source_label = "Kimi Code usage API"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.explicit_api_key = api_key
        self.client = client or KimiUsageClient()
        self.environ = os.environ if environ is None else environ

    def is_available(self) -> bool:
        return bool(self._api_key())

    def fetch(self, now: datetime) -> AccountSnapshot:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError("Kimi API key is not configured")
        return parse_kimi_usage(self.client.fetch(api_key), now=now)

    def _api_key(self) -> Optional[str]:
        for candidate in (
            self.explicit_api_key,
            self.environ.get("KIMI_CODE_API_KEY"),
            self.environ.get("KIMI_API_KEY"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None


def parse_kimi_usage(payload: Dict[str, Any], *, now: datetime) -> AccountSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("Kimi usage payload must be an object")
    quotas = []
    limits = payload.get("limits")
    if limits is not None and not isinstance(limits, list):
        raise ValueError("limits must be a list")
    for index, row in enumerate(limits or []):
        if not isinstance(row, dict):
            raise ValueError("limits entries must be objects")
        window = row.get("window")
        detail = row.get("detail")
        if not isinstance(window, dict) or not isinstance(detail, dict):
            raise ValueError("Kimi rolling limits require window and detail objects")
        duration = _integer(window.get("duration"), "duration")
        unit = window.get("timeUnit")
        minutes = _duration_minutes(duration, unit)
        quotas.append(
            _quota_from_detail(
                "rolling-%s" % index,
                "%s requests" % _duration_label(minutes),
                detail,
                period_label=_duration_label(minutes),
            )
        )
    overall = payload.get("usage")
    if not isinstance(overall, dict):
        raise ValueError("usage must be an object")
    quotas.append(
        _quota_from_detail(
            "weekly-requests",
            "Weekly requests",
            overall,
            period_label="Subscription cycle",
        )
    )
    return AccountSnapshot(
        id="kimi-code",
        provider_id=KIMI_DESCRIPTOR.id,
        provider_name=KIMI_DESCRIPTOR.display_name,
        client_name=KIMI_DESCRIPTOR.client_name,
        account_kind=KIMI_DESCRIPTOR.account_kind,
        status="available",
        source_type="official_api",
        source_label="Kimi Code usage API",
        fetched_at=_to_iso(now),
        stale_after_seconds=KIMI_DESCRIPTOR.stale_after_seconds,
        plan_name="Kimi Code",
        quotas=tuple(quotas),
    )


def fetch_kimi_outcome(
    api_key: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    client: Optional[Any] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    return run_provider(
        KIMI_DESCRIPTOR,
        [KimiUsageStrategy(api_key=api_key, client=client, environ=environ)],
        now=current,
    )


def _quota_from_detail(
    quota_id: str,
    label: str,
    detail: Dict[str, Any],
    *,
    period_label: str,
) -> QuotaWindow:
    limit = _number(detail.get("limit"), "limit")
    used = _number(detail.get("used"), "used")
    remaining = _number(detail.get("remaining"), "remaining")
    remaining_percent = (remaining / limit * 100) if limit > 0 else None
    return QuotaWindow(
        id=quota_id,
        label=label,
        unit="requests",
        used=used,
        limit=limit,
        remaining=remaining,
        remaining_percent=remaining_percent,
        resets_at=normalize_timestamp(detail.get("resetTime")),
        period_label=period_label,
        accuracy="exact",
    )


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("%s must be a non-negative number" % name)
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("%s must be a non-negative number" % name) from None
    if not number.is_finite() or number < 0:
        raise ValueError("%s must be a non-negative number" % name)
    result = float(number)
    return int(result) if result.is_integer() else result


def _integer(value: Any, name: str) -> int:
    number = _number(value, name)
    if not float(number).is_integer() or number <= 0:
        raise ValueError("%s must be a positive integer" % name)
    return int(number)


def _duration_minutes(duration: int, unit: Any) -> int:
    multipliers = {
        "TIME_UNIT_MINUTE": 1,
        "TIME_UNIT_HOUR": 60,
        "TIME_UNIT_DAY": 1440,
    }
    multiplier = multipliers.get(unit)
    if multiplier is None:
        raise ValueError("unsupported Kimi time unit")
    return duration * multiplier


def _duration_label(minutes: int) -> str:
    if minutes % 1440 == 0:
        return "%s-day" % (minutes // 1440)
    if minutes % 60 == 0:
        return "%s-hour" % (minutes // 60)
    return "%s-minute" % minutes


def _to_iso(value: datetime) -> str:
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
