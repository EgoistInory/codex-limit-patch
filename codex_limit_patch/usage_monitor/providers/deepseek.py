from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..models import AccountSnapshot, MetricComponent, QuotaWindow
from .base import ProviderDescriptor, ProviderFetchOutcome, run_provider


DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
MAX_RESPONSE_BYTES = 1024 * 1024
DEEPSEEK_DESCRIPTOR = ProviderDescriptor(
    id="deepseek",
    display_name="DeepSeek",
    client_name=None,
    account_kind="api",
    stale_after_seconds=900,
)


class DeepSeekBalanceClient:
    def __init__(
        self,
        *,
        endpoint: str = DEEPSEEK_BALANCE_URL,
        timeout_sec: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.deepseek.com"
            or parsed.path != "/user/balance"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("DeepSeek balance endpoint must use the official HTTPS URL")
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.max_response_bytes = max_response_bytes
        self.opener = opener

    def fetch(self, api_key: str) -> Dict[str, Any]:
        key = api_key.strip()
        if not key:
            raise ValueError("DeepSeek API key is required")
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
            raise RuntimeError(
                "DeepSeek balance API returned HTTP %s" % exc.code
            ) from None
        except (URLError, OSError):
            raise RuntimeError("DeepSeek balance API request failed") from None
        if len(raw) > self.max_response_bytes:
            raise RuntimeError("DeepSeek balance API response is too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("DeepSeek balance API returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("DeepSeek balance API returned an invalid object")
        return payload


class DeepSeekBalanceStrategy:
    id = "deepseek.balance-api"
    source_type = "official_api"
    source_label = "DeepSeek balance API"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.explicit_api_key = api_key
        self.client = client or DeepSeekBalanceClient()
        self.environ = os.environ if environ is None else environ

    def is_available(self) -> bool:
        return bool(self._api_key())

    def fetch(self, now: datetime) -> AccountSnapshot:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError("DeepSeek API key is not configured")
        payload = self.client.fetch(api_key)
        return parse_deepseek_balance(payload, now=now)

    def _api_key(self) -> Optional[str]:
        candidates = (
            self.explicit_api_key,
            self.environ.get("DEEPSEEK_API_KEY"),
            self.environ.get("DEEPSEEK_KEY"),
        )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None


def parse_deepseek_balance(
    payload: Dict[str, Any],
    *,
    now: datetime,
) -> AccountSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("DeepSeek balance payload must be an object")
    is_available = payload.get("is_available")
    if not isinstance(is_available, bool):
        raise ValueError("is_available must be a boolean")
    rows = payload.get("balance_infos")
    if not isinstance(rows, list) or not rows:
        raise ValueError("balance_infos must be a non-empty list")
    quotas = []
    currencies = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("balance_infos entries must be objects")
        currency = row.get("currency")
        if currency not in ("CNY", "USD"):
            raise ValueError("currency must be CNY or USD")
        if currency in currencies:
            raise ValueError("balance_infos contains a duplicate currency")
        currencies.add(currency)
        total = _decimal_value(row, "total_balance")
        granted = _decimal_value(row, "granted_balance")
        topped_up = _decimal_value(row, "topped_up_balance")
        quotas.append(
            QuotaWindow(
                id="balance-%s" % currency.lower(),
                label="%s API balance" % currency,
                unit=currency,
                remaining=total,
                components=(
                    MetricComponent("Granted", granted, currency),
                    MetricComponent("Paid", topped_up, currency),
                ),
                accuracy="exact",
            )
        )
    return AccountSnapshot(
        id="deepseek-api",
        provider_id=DEEPSEEK_DESCRIPTOR.id,
        provider_name=DEEPSEEK_DESCRIPTOR.display_name,
        client_name=DEEPSEEK_DESCRIPTOR.client_name,
        account_kind=DEEPSEEK_DESCRIPTOR.account_kind,
        status="available" if is_available else "degraded",
        source_type="official_api",
        source_label="DeepSeek balance API",
        fetched_at=_to_iso(now),
        stale_after_seconds=DEEPSEEK_DESCRIPTOR.stale_after_seconds,
        quotas=tuple(quotas),
        message=(
            None
            if is_available
            else "DeepSeek reports that the balance is unavailable for API calls."
        ),
    )


def fetch_deepseek_outcome(
    api_key: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    client: Optional[Any] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> ProviderFetchOutcome:
    current = now or datetime.now(timezone.utc)
    strategy = DeepSeekBalanceStrategy(
        api_key=api_key,
        client=client,
        environ=environ,
    )
    return run_provider(DEEPSEEK_DESCRIPTOR, [strategy], now=current)


def _decimal_value(row: Dict[str, Any], key: str) -> float:
    raw = row.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise ValueError("%s must be a non-negative decimal" % key)
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError("%s must be a non-negative decimal" % key) from None
    if not value.is_finite() or value < 0:
        raise ValueError("%s must be a non-negative decimal" % key)
    return float(value)


def _to_iso(value: datetime) -> str:
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
