from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .alerts import UsageAlert, evaluate_alerts
from .models import load_snapshots


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "demos" / "milestone-1" / "snapshots.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "demos" / "milestone-1" / "demo-data.js"


def generate_demo_data(
    input_path: Path,
    output_path: Path,
    *,
    now: datetime,
) -> Path:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    snapshots = load_snapshots(raw.get("accounts", []))
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
    payload = {
        "schema_version": raw.get("schema_version", 1),
        "demo": True,
        "generated_at": _to_iso(now),
        "accounts": [snapshot.to_dict() for snapshot in snapshots],
        "alerts": [alert.to_dict() for alert in alerts],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "window.USAGE_MONITOR_DEMO = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the usage monitor browser demo data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--now", help="Optional ISO timestamp for reproducible output.")
    args = parser.parse_args(argv)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    result = generate_demo_data(args.input, args.output, now=now)
    try:
        shown_path = result.relative_to(Path.cwd())
    except ValueError:
        shown_path = result
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
