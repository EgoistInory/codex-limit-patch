from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .collector import build_three_source_payload, collect_supported_payload
from .live_demo import write_browser_payload


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "demos" / "milestone-1" / "snapshots.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "demos" / "milestone-4" / "demo-data.js"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate live AI usage and quota data for supported providers."
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex-bin")
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--gemini-config-dir", type=Path)
    parser.add_argument(
        "--deepseek-api-key-env",
        help="Environment variable containing the DeepSeek API key.",
    )
    parser.add_argument("--kimi-api-key-env")
    parser.add_argument("--zhipu-api-key-env")
    parser.add_argument("--minimax-api-key-env")
    parser.add_argument("--now", help="Optional ISO timestamp for reproducible output.")
    args = parser.parse_args(argv)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)

    def explicit_key(env_name: Optional[str]):
        if not env_name:
            return None, None
        return os.environ.get(env_name), {}

    deepseek_key, deepseek_environ = explicit_key(args.deepseek_api_key_env)
    kimi_key, kimi_environ = explicit_key(args.kimi_api_key_env)
    zhipu_key, zhipu_environ = explicit_key(args.zhipu_api_key_env)
    minimax_key, minimax_environ = explicit_key(args.minimax_api_key_env)

    payload = collect_supported_payload(
        args.fixture,
        codex_bin=args.codex_bin,
        claude_config_dir=args.claude_config_dir,
        gemini_config_dir=args.gemini_config_dir,
        deepseek_api_key=deepseek_key,
        deepseek_environ=deepseek_environ,
        kimi_api_key=kimi_key,
        kimi_environ=kimi_environ,
        zhipu_api_key=zhipu_key,
        zhipu_environ=zhipu_environ,
        minimax_api_key=minimax_key,
        minimax_environ=minimax_environ,
        now=now,
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
