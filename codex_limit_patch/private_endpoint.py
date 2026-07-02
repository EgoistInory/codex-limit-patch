from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .parser import normalize_reset_bank


ENDPOINT = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


class PrivateEndpointError(RuntimeError):
    pass


def fetch_private_endpoint_reset_bank(
    *,
    snapshot_at: datetime | None = None,
    now: datetime | None = None,
    debug: Callable[[str], None] | None = None,
):
    snapshot = snapshot_at or datetime.now(timezone.utc)
    current = now or snapshot
    auth = _read_auth_json()
    access_token = _find_access_token(auth)
    if not access_token:
        raise PrivateEndpointError("tokens.access_token not found in Codex auth")

    headers = {
        "Authorization": "Bearer " + access_token,
        "Accept": "application/json",
        "User-Agent": "CodexLimitPatch/0.1 experimental-private-endpoint",
    }
    account_id = _find_account_id(auth)
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    request = urllib.request.Request(ENDPOINT, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise PrivateEndpointError(f"private endpoint returned HTTP {exc.code}") from exc
    except OSError as exc:
        raise PrivateEndpointError(str(exc)) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PrivateEndpointError("private endpoint returned non-JSON response") from exc

    state = normalize_reset_bank(
        payload,
        snapshot_at=snapshot,
        now=current,
        data_source="private_endpoint",
        source_label="private backend endpoint, experimental",
        details_message="Source: private backend endpoint, experimental",
        debug=debug,
    )
    return state


def _read_auth_json() -> dict[str, Any]:
    path = Path.home() / ".codex" / "auth.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise PrivateEndpointError("Codex auth file has unsupported shape")
    return payload


def _find_access_token(value: Any) -> str | None:
    if isinstance(value, dict):
        tokens = value.get("tokens")
        if isinstance(tokens, dict):
            token = tokens.get("access_token") or tokens.get("accessToken")
            if isinstance(token, str) and token:
                return token
        for key in ("access_token", "accessToken"):
            token = value.get(key)
            if isinstance(token, str) and token:
                return token
        for child in value.values():
            found = _find_access_token(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_access_token(child)
            if found:
                return found
    return None


def _find_account_id(value: Any) -> str | None:
    candidates: list[tuple[str, str]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                key_text = str(key)
                lower = key_text.lower()
                if isinstance(child, str) and child:
                    if lower in {
                        "account_id",
                        "accountid",
                        "chatgpt_account_id",
                        "active_account_id",
                        "current_account_id",
                    } or ("account" in lower and lower.endswith("id")):
                        candidates.append((path + "/" + key_text, child))
                walk(child, path + "/" + key_text)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, path + f"[{index}]")

    walk(value)
    for path, candidate in candidates:
        lowered = path.lower()
        if "active" in lowered or "current" in lowered or "chatgpt" in lowered:
            return candidate
    return candidates[0][1] if candidates else None
