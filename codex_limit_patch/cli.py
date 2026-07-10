from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import CodexAppServerClient, CodexAppServerError
from .display import render_expanded, render_pill
from .local_probe import probe_local_rate_limits, probe_local_safe_sources
from .parser import build_codex_limit_state, to_plain
from .private_endpoint import PrivateEndpointError, fetch_private_endpoint_reset_bank


DEFAULT_SETTINGS = {
    "resetBank": {
        "showInPill": True,
        "showDetailsInExpanded": True,
        "warnExpireWithinHours": 72,
        "dangerExpireWithinHours": 24,
        "showUnknownDetails": True,
        "enablePrivateEndpoint": False,
        "privateEndpointWarningAccepted": False,
    }
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show local Codex quota and reset bank state.")
    parser.add_argument(
        "--mode",
        choices=("pill", "expanded", "json"),
        default="expanded",
        help="Output mode.",
    )
    parser.add_argument("--codex-bin", help="Path to codex binary. Defaults to PATH or CODEX_BIN.")
    parser.add_argument("--input-json", help="Read a saved account/rateLimits/read response.")
    parser.add_argument("--settings", help="Optional settings.json path.")
    parser.add_argument("--debug-log", help="Write reset bank raw shape diagnostics to this file.")
    args = parser.parse_args(argv)

    settings = _load_settings(args.settings)
    debug = _debug_writer(args.debug_log)
    snapshot = datetime.now(timezone.utc)

    if args.input_json:
        with Path(args.input_json).open("r", encoding="utf-8-sig") as handle:
            response: dict[str, Any] = json.load(handle)
    else:
        response = _read_rate_limits(args.codex_bin, debug=debug)

    state = build_codex_limit_state(response, snapshot_at=snapshot, debug=debug)
    _augment_reset_bank(state, settings=settings, snapshot=snapshot, debug=debug)
    if args.mode == "pill":
        print(render_pill(state, settings=settings))
    elif args.mode == "json":
        print(json.dumps(to_plain(state), ensure_ascii=False, indent=2))
    else:
        print(render_expanded(state, settings=settings))
    return 0


def _read_rate_limits(codex_bin: str | None, *, debug) -> dict[str, Any]:
    try:
        return CodexAppServerClient(codex_bin).read_rate_limits()
    except (CodexAppServerError, OSError) as exc:
        fallback = probe_local_rate_limits(debug=debug)
        if fallback is None:
            raise
        if isinstance(exc, OSError):
            detail = f"unable to start Codex binary (errno {exc.errno})"
        else:
            detail = str(exc).splitlines()[0].strip() or exc.__class__.__name__
            if len(detail) > 200:
                detail = detail[:197] + "..."
        warning = f"Live rate limits unavailable: {detail}"
        metadata = fallback.setdefault("_codexLimitPatch", {})
        metadata["warning"] = warning
        if debug:
            debug(f"using local rollout rate limit fallback: {detail}")
        return fallback


def _augment_reset_bank(
    state,
    *,
    settings: dict[str, Any],
    snapshot: datetime,
    debug,
) -> None:
    bank = state.resetBank
    if bank is None:
        return
    if bank.detailsAvailable:
        return

    local_state = probe_local_safe_sources(
        snapshot_at=snapshot,
        now=snapshot,
        debug=debug,
    )
    if local_state is not None and local_state.detailsAvailable:
        if bank.availableCount is not None:
            local_state.availableCount = bank.availableCount
        state.resetBank = local_state
        state.resetCredits = local_state.availableCount
        return

    reset_settings = settings.get("resetBank", {})
    enabled = bool(reset_settings.get("enablePrivateEndpoint"))
    accepted = bool(reset_settings.get("privateEndpointWarningAccepted"))
    if not enabled:
        bank.detailsMessage = (
            "Details: not provided by supported Codex app-server\n"
            "Reset credit details not available from local safe sources."
        )
        return
    if not accepted:
        bank.detailsMessage = (
            "Private endpoint disabled: set privateEndpointWarningAccepted=true "
            "after reviewing the experimental risk."
        )
        return

    try:
        private_state = fetch_private_endpoint_reset_bank(
            snapshot_at=snapshot,
            now=snapshot,
            debug=debug,
        )
    except PrivateEndpointError as exc:
        bank.detailsMessage = f"Private endpoint unavailable: {exc}"
        return
    if bank.availableCount is not None:
        private_state.availableCount = bank.availableCount
    state.resetBank = private_state
    state.resetCredits = private_state.availableCount


def _load_settings(path: str | None) -> dict[str, Any]:
    if not path:
        return DEFAULT_SETTINGS
    settings_path = Path(path)
    if not settings_path.exists():
        return DEFAULT_SETTINGS
    with settings_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    merged = dict(DEFAULT_SETTINGS)
    reset_bank = dict(DEFAULT_SETTINGS["resetBank"])
    reset_bank.update(data.get("resetBank", {}))
    merged["resetBank"] = reset_bank
    return merged


def _debug_writer(path: str | None):
    if not path:
        return None
    log_path = Path(path)

    def write(message: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")

    return write


if __name__ == "__main__":
    raise SystemExit(main())
