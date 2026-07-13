from __future__ import annotations

import argparse
import importlib
import os
import platform
import queue
import re
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .collector import collect_three_source_payload
from .live_demo import write_browser_payload
from .menubar_model import MenuPresentation, build_menu_presentation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "demos" / "milestone-1" / "snapshots.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "demos" / "milestone-4" / "demo-data.js"
DEFAULT_DASHBOARD = PROJECT_ROOT / "demos" / "milestone-4" / "index-live.html"
PROVIDERS = (
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("deepseek", "DeepSeek"),
)


@dataclass
class MenuBarOptions:
    refresh_sec: int = 60
    codex_bin: Optional[str] = None
    claude_config_dir: Optional[Path] = None
    deepseek_api_key_env: Optional[str] = None
    fixture_path: Path = DEFAULT_FIXTURE
    output_path: Path = DEFAULT_OUTPUT
    dashboard_path: Path = DEFAULT_DASHBOARD

    def __post_init__(self) -> None:
        self.refresh_sec = max(15, int(self.refresh_sec))


class UsageMenuBarApp:
    def __init__(
        self,
        options: MenuBarOptions,
        *,
        rumps_module: Any,
        collector: Callable[..., Dict[str, Any]] = collect_three_source_payload,
        thread_factory: Callable[..., Any] = threading.Thread,
        browser_opener: Callable[[str], Any] = webbrowser.open,
    ) -> None:
        self.options = options
        self.rumps = rumps_module
        self.collector = collector
        self.thread_factory = thread_factory
        self.browser_opener = browser_opener
        self.results: queue.Queue = queue.Queue()
        self.refreshing = False
        self.last_payload: Optional[Dict[str, Any]] = None

        self.app = self.rumps.App("AI Usage Monitor", title="AI …", quit_button=None)
        self.provider_items = {}
        self.source_items = {}
        menu: List[Any] = []
        for provider_id, label in PROVIDERS:
            item = self.rumps.MenuItem("○ %s · Loading…" % label)
            source = self.rumps.MenuItem("Source · Waiting for refresh")
            item.add(source)
            self.provider_items[provider_id] = item
            self.source_items[provider_id] = source
            menu.append(item)
        self.updated_item = self.rumps.MenuItem("Update pending")
        self.status_item = self.rumps.MenuItem("Status · Starting")
        self.refresh_item = self.rumps.MenuItem("Refresh Now", callback=self.schedule_refresh)
        self.dashboard_item = self.rumps.MenuItem("Open Dashboard", callback=self.open_dashboard)
        self.quit_item = self.rumps.MenuItem("Quit", callback=self.quit)
        menu.extend(
            [
                None,
                self.updated_item,
                self.status_item,
                None,
                self.refresh_item,
                self.dashboard_item,
                self.quit_item,
            ]
        )
        self.app.menu = menu
        self.refresh_timer = self.rumps.Timer(self.schedule_refresh, options.refresh_sec)
        self.poll_timer = self.rumps.Timer(self.poll_results, 0.25)

    def run(self) -> None:
        self.refresh_timer.start()
        self.poll_timer.start()
        self.schedule_refresh()
        self.app.run()

    def schedule_refresh(self, _sender: Any = None) -> None:
        if self.refreshing:
            return
        self.refreshing = True
        self.status_item.title = "Status · Refreshing…"
        self.thread_factory(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            deepseek_key = None
            deepseek_environ = os.environ
            if self.options.deepseek_api_key_env:
                deepseek_key = os.environ.get(self.options.deepseek_api_key_env)
                deepseek_environ = {}
            payload = self.collector(
                fixture_path=self.options.fixture_path,
                codex_bin=self.options.codex_bin,
                claude_config_dir=self.options.claude_config_dir,
                deepseek_api_key=deepseek_key,
                deepseek_environ=deepseek_environ,
            )
            write_browser_payload(payload, self.options.output_path)
            self.results.put(("ok", payload))
        except Exception as exc:
            self.results.put(("error", sanitize_error(exc)))

    def poll_results(self, _sender: Any = None) -> None:
        try:
            kind, value = self.results.get_nowait()
        except queue.Empty:
            return
        self.refreshing = False
        if kind == "ok":
            self.last_payload = value
            self._apply(build_menu_presentation(value))
            return
        if self.last_payload is not None:
            self._apply(build_menu_presentation(self.last_payload, error_message=value))
        else:
            self.app.title = "AI ×"
            self.status_item.title = "Error · %s" % value

    def _apply(self, presentation: MenuPresentation) -> None:
        self.app.title = presentation.title
        rows = {row.provider_id: row for row in presentation.rows}
        symbols = {"available": "●", "degraded": "▲", "unavailable": "×"}
        for provider_id, label in PROVIDERS:
            row = rows.get(provider_id)
            if row is None:
                self.provider_items[provider_id].title = "○ %s · No data" % label
                self.source_items[provider_id].title = "Source · Unknown"
                continue
            symbol = symbols.get(row.status, "○")
            self.provider_items[provider_id].title = "%s %s · %s" % (
                symbol,
                row.label,
                row.detail,
            )
            self.source_items[provider_id].title = "Source · %s" % row.source_label
        self.updated_item.title = presentation.updated_label
        if presentation.error_message:
            self.status_item.title = "Error · %s" % presentation.error_message
        else:
            self.status_item.title = "Status · Auto-refresh every %ss" % self.options.refresh_sec

    def open_dashboard(self, _sender: Any = None) -> None:
        if self.last_payload is not None:
            write_browser_payload(self.last_payload, self.options.output_path)
        self.browser_opener(self.options.dashboard_path.resolve().as_uri())

    def quit(self, _sender: Any = None) -> None:
        self.rumps.quit_application()


def require_macos(system_name: Optional[str] = None) -> None:
    current = system_name or platform.system()
    if current != "Darwin":
        raise RuntimeError("The menu-bar monitor is available only on macOS.")


def load_rumps() -> Any:
    try:
        return importlib.import_module("rumps")
    except ImportError:
        raise RuntimeError(
            "The macOS menu-bar dependency is missing. Install with: "
            "pip install -e '.[macos-menubar]'"
        ) from None


def sanitize_error(exc: Exception) -> str:
    message = str(exc).splitlines()[0].strip() or exc.__class__.__name__
    message = re.sub(r"(?i)\bbearer\s+\S+", "Bearer [redacted]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]{6,}\b", "[redacted]", message)
    if len(message) > 160:
        message = message[:157] + "..."
    return message


def main(argv: Optional[List[str]] = None) -> int:
    require_macos()
    args = _build_parser().parse_args(argv)
    options = MenuBarOptions(
        refresh_sec=args.refresh_sec,
        codex_bin=args.codex_bin,
        claude_config_dir=args.claude_config_dir,
        deepseek_api_key_env=args.deepseek_api_key_env,
        fixture_path=args.fixture,
        output_path=args.output,
        dashboard_path=args.dashboard,
    )
    UsageMenuBarApp(options, rumps_module=load_rumps()).run()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show AI usage and quota status in the macOS menu bar."
    )
    parser.add_argument("--refresh-sec", type=int, default=60)
    parser.add_argument("--codex-bin")
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--deepseek-api-key-env")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
