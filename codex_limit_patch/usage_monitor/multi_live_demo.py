from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .alerts import UsageAlert, evaluate_alerts
from .live_demo import write_browser_payload
from .models import AccountSnapshot, load_snapshots
from .providers.base import ProviderFetchOutcome
from .providers.claude import fetch_claude_outcome
from .providers.codex import fetch_codex_outcome


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "demos" / "milestone-1" / "snapshots.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "demos" / "milestone-3" / "demo-data.js"


def build_multi_live_payload(
    fixture_path: Path,
    *,
    outcomes: Sequence[ProviderFetchOutcome],
    now: datetime,
) -> Dict[str, Any]:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixtures = load_snapshots(raw.get("accounts", []))
    outcomes_by_id: Dict[str, ProviderFetchOutcome] = {}
    live_provider_ids: List[str] = []
    for outcome in outcomes:
        provider_id = outcome.descriptor.id
        if provider_id in outcomes_by_id:
            raise ValueError("duplicate provider outcome: %s" % provider_id)
        outcomes_by_id[provider_id] = outcome
        live_provider_ids.append(provider_id)

    accounts: List[Dict[str, Any]] = []
    snapshots: List[AccountSnapshot] = []
    inserted = set()
    for fixture in fixtures:
        outcome = outcomes_by_id.get(fixture.provider_id)
        if outcome is None:
            snapshot = fixture
            account = fixture.to_dict()
            account["demo"] = True
        else:
            snapshot = outcome.snapshot
            account = snapshot.to_dict()
            account["demo"] = False
            inserted.add(fixture.provider_id)
        snapshots.append(snapshot)
        accounts.append(account)
    for provider_id in live_provider_ids:
        if provider_id in inserted:
            continue
        snapshot = outcomes_by_id[provider_id].snapshot
        account = snapshot.to_dict()
        account["demo"] = False
        snapshots.append(snapshot)
        accounts.append(account)

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
        "live_provider_ids": live_provider_ids,
        "generated_at": _to_iso(now),
        "accounts": accounts,
        "alerts": [alert.to_dict() for alert in alerts],
        "fetch_attempts": {
            provider_id: [
                {
                    "strategy_id": attempt.strategy_id,
                    "source_type": attempt.source_type,
                    "source_label": attempt.source_label,
                    "available": attempt.available,
                    "success": attempt.success,
                    "error_message": attempt.error_message,
                }
                for attempt in outcomes_by_id[provider_id].attempts
            ]
            for provider_id in live_provider_ids
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a dashboard with live Codex and Claude Code usage."
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex-bin")
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--now", help="Optional ISO timestamp for reproducible output.")
    args = parser.parse_args(argv)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    outcomes = [
        fetch_codex_outcome(codex_bin=args.codex_bin, now=now),
        fetch_claude_outcome(config_dir=args.claude_config_dir, now=now),
    ]
    payload = build_multi_live_payload(args.fixture, outcomes=outcomes, now=now)
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
