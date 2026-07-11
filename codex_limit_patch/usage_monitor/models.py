from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union


Number = Union[int, float]


@dataclass(frozen=True)
class QuotaWindow:
    id: str
    label: str
    unit: str
    used: Optional[Number] = None
    limit: Optional[Number] = None
    remaining: Optional[Number] = None
    remaining_percent: Optional[Number] = None
    resets_at: Optional[str] = None
    period_label: Optional[str] = None
    accuracy: str = "exact"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuotaWindow":
        return cls(
            id=_required_str(data, "id"),
            label=_required_str(data, "label"),
            unit=_required_str(data, "unit"),
            used=_optional_number(data, "used"),
            limit=_optional_number(data, "limit"),
            remaining=_optional_number(data, "remaining"),
            remaining_percent=_optional_number(data, "remaining_percent"),
            resets_at=_optional_str(data, "resets_at"),
            period_label=_optional_str(data, "period_label"),
            accuracy=_optional_str(data, "accuracy") or "exact",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "used": self.used,
            "limit": self.limit,
            "remaining": self.remaining,
            "remaining_percent": self.remaining_percent,
            "resets_at": self.resets_at,
            "period_label": self.period_label,
            "accuracy": self.accuracy,
        }


@dataclass(frozen=True)
class ModelUsage:
    model_id: str
    display_name: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost: Optional[Number] = None
    currency: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelUsage":
        return cls(
            model_id=_required_str(data, "model_id"),
            display_name=_required_str(data, "display_name"),
            input_tokens=_optional_int(data, "input_tokens"),
            output_tokens=_optional_int(data, "output_tokens"),
            cost=_optional_number(data, "cost"),
            currency=_optional_str(data, "currency"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost": self.cost,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class AccountSnapshot:
    id: str
    provider_id: str
    provider_name: str
    account_kind: str
    status: str
    source_type: str
    source_label: str
    fetched_at: str
    stale_after_seconds: int
    client_name: Optional[str] = None
    quotas: Tuple[QuotaWindow, ...] = ()
    models: Tuple[ModelUsage, ...] = ()
    requests_today: Optional[int] = None
    tokens_today: Optional[int] = None
    cost_today: Optional[Number] = None
    currency: Optional[str] = None
    message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountSnapshot":
        account_id = _required_str(data, "id")
        provider_id = _required_str(data, "provider_id")
        provider_name = _required_str(data, "provider_name")
        account_kind = _required_str(data, "account_kind")
        status = _required_str(data, "status")
        source_type = _required_str(data, "source_type")
        source_label = _required_str(data, "source_label")
        fetched_at = _required_str(data, "fetched_at")
        stale_after = _required_int(data, "stale_after_seconds")
        if stale_after <= 0:
            raise ValueError("stale_after_seconds must be greater than zero")
        quotas = _object_list(data, "quotas")
        models = _object_list(data, "models")
        return cls(
            id=account_id,
            provider_id=provider_id,
            provider_name=provider_name,
            account_kind=account_kind,
            status=status,
            source_type=source_type,
            source_label=source_label,
            fetched_at=fetched_at,
            stale_after_seconds=stale_after,
            client_name=_optional_str(data, "client_name"),
            quotas=tuple(QuotaWindow.from_dict(item) for item in quotas),
            models=tuple(ModelUsage.from_dict(item) for item in models),
            requests_today=_optional_int(data, "requests_today"),
            tokens_today=_optional_int(data, "tokens_today"),
            cost_today=_optional_number(data, "cost_today"),
            currency=_optional_str(data, "currency"),
            message=_optional_str(data, "message"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "account_kind": self.account_kind,
            "status": self.status,
            "source_type": self.source_type,
            "source_label": self.source_label,
            "fetched_at": self.fetched_at,
            "stale_after_seconds": self.stale_after_seconds,
            "client_name": self.client_name,
            "quotas": [quota.to_dict() for quota in self.quotas],
            "models": [model.to_dict() for model in self.models],
            "requests_today": self.requests_today,
            "tokens_today": self.tokens_today,
            "cost_today": self.cost_today,
            "currency": self.currency,
            "message": self.message,
        }


def load_snapshots(data: List[Dict[str, Any]]) -> List[AccountSnapshot]:
    if not isinstance(data, list):
        raise ValueError("snapshots must be a list")
    return [AccountSnapshot.from_dict(item) for item in data]


def _required_str(data: Dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % key)
    return value.strip()


def _optional_str(data: Dict[str, Any], key: str) -> Optional[str]:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("%s must be a string or null" % key)
    return value.strip() or None


def _required_int(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be an integer" % key)
    return value


def _optional_int(data: Dict[str, Any], key: str) -> Optional[int]:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be an integer or null" % key)
    return value


def _optional_number(data: Dict[str, Any], key: str) -> Optional[Number]:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number or null" % key)
    return value


def _object_list(data: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("%s must be a list of objects" % key)
    return value
