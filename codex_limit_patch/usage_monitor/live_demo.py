from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .alerts import UsageAlert, evaluate_alerts
from .models import AccountSnapshot, load_snapshots
from .providers.base import ProviderFetchOutcome
from .providers.codex import fetch_codex_outcome


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "demos" / "milestone-1" / "snapshots.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "demos" / "milestone-2" / "demo-data.js"


def build_live_payload(
    fixture_path: Path,
    *,
    codex_outcome: ProviderFetchOutcome,
    now: datetime,
) -> Dict[str, Any]:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixtures = load_snapshots(raw.get("accounts", []))
    snapshots: List[AccountSnapshot] = []
    accounts: List[Dict[str, Any]] = []
    replaced = False
    for fixture in fixtures:
        if fixture.provider_id == "openai":
            snapshot = codex_outcome.snapshot
            account = snapshot.to_dict()
            account["demo"] = False
            snapshots.append(snapshot)
            accounts.append(account)
            replaced = True
            continue
        account = fixture.to_dict()
        account["demo"] = True
        snapshots.append(fixture)
        accounts.append(account)
    if not replaced:
        account = codex_outcome.snapshot.to_dict()
        account["demo"] = False
        snapshots.insert(0, codex_outcome.snapshot)
        accounts.insert(0, account)

    alerts: List[UsageAlert] = []
    for snapshot in snapshots:
        alerts.extend(evaluate_alerts(snapshot, now=now))
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(
        key=lambda alert: (
            severity_order.get(alert.severity, 99),
            alert.kind,
            alert.account_id,
            alert.quota_id or "",
        )
    )

    return {
        "schema_version": raw.get("schema_version", 1),
        "demo": True,
        "mixed_sources": True,
        "live_provider_ids": ["openai"],
        "generated_at": _to_iso(now),
        "accounts": accounts,
        "alerts": [alert.to_dict() for alert in alerts],
        "fetch_attempts": {
            codex_outcome.descriptor.id: [
                {
                    "strategy_id": attempt.strategy_id,
                    "source_type": attempt.source_type,
                    "source_label": attempt.source_label,
                    "available": attempt.available,
                    "success": attempt.success,
                    "error_message": attempt.error_message,
                }
                for attempt in codex_outcome.attempts
            ]
        },
    }


def write_browser_payload(payload: Dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "window.USAGE_MONITOR_DEMO = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a mixed-source dashboard with live local Codex limits."
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex-bin")
    parser.add_argument("--now", help="Optional ISO timestamp for reproducible output.")
    args = parser.parse_args(argv)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    outcome = fetch_codex_outcome(codex_bin=args.codex_bin, now=now)
    payload = build_live_payload(args.fixture, codex_outcome=outcome, now=now)
    output = write_browser_payload(payload, args.output)
    try:
        shown_path = output.relative_to(Path.cwd())
    except ValueError:
        shown_path = output
    print("Wrote %s" % shown_path)
    return 0


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("--now must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_iso(value: datetime) -> str:
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
