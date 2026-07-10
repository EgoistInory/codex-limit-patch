from __future__ import annotations

import argparse
import platform
import queue
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .cli import (
    _augment_reset_bank,
    _debug_writer,
    _load_settings,
    _read_rate_limits,
)
from .display import render_expanded, render_pill
from .parser import build_codex_limit_state


DEFAULT_REFRESH_SECONDS = 60
DEFAULT_MARGIN = 14


@dataclass
class OverlayOptions:
    mode: str
    refresh_sec: int
    codex_bin: str | None
    settings_path: str | None
    debug_log: str | None
    track_codex: bool
    geometry: str | None
    opacity: float


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    options = OverlayOptions(
        mode=args.mode,
        refresh_sec=max(10, args.refresh_sec),
        codex_bin=args.codex_bin,
        settings_path=args.settings,
        debug_log=args.debug_log,
        track_codex=not args.no_track_codex,
        geometry=args.geometry,
        opacity=min(1.0, max(0.2, args.opacity)),
    )
    LimitOverlayApp(options).run()
    return 0


class LimitOverlayApp:
    def __init__(self, options: OverlayOptions):
        self.options = options
        self.settings = _load_settings(options.settings_path)
        self.debug = _debug_writer(options.debug_log)
        self.results: queue.Queue[tuple[str, str]] = queue.Queue()
        self.refreshing = False
        self.last_text = "Codex limits loading..."

        self.root = tk.Tk()
        self.root.title("Codex Limit Patch")
        self.root.configure(bg="#111111")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", options.opacity)
        self.root.resizable(False, False)
        self.root.overrideredirect(True)

        self.label = tk.Label(
            self.root,
            text=self.last_text,
            justify="left",
            anchor="w",
            bg="#111111",
            fg="#f5f5f5",
            activebackground="#111111",
            activeforeground="#f5f5f5",
            font=("Menlo", 12),
            padx=12,
            pady=9,
        )
        self.label.pack()
        self._bind_window_controls()

        if options.geometry:
            self.root.geometry(options.geometry)
        else:
            self._place_default()

    def run(self) -> None:
        self._refresh_async()
        self._poll_results()
        self.root.mainloop()

    def _bind_window_controls(self) -> None:
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.bind("<Control-q>", lambda _event: self.root.destroy())
        self.root.bind("<ButtonPress-1>", self._start_drag)
        self.root.bind("<B1-Motion>", self._drag)
        self.root.bind("<Double-Button-1>", lambda _event: self._refresh_async())

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_start = (
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
        )

    def _drag(self, event: tk.Event) -> None:
        start_x, start_y, window_x, window_y = getattr(
            self,
            "_drag_start",
            (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y()),
        )
        x = window_x + event.x_root - start_x
        y = window_y + event.y_root - start_y
        self.root.geometry(f"+{x}+{y}")

    def _refresh_async(self) -> None:
        if self.refreshing:
            return
        self.refreshing = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            text = _read_overlay_text(
                mode=self.options.mode,
                codex_bin=self.options.codex_bin,
                settings=self.settings,
                debug=self.debug,
            )
            self.results.put(("ok", text))
        except Exception as exc:
            self.results.put(("error", _error_text(exc)))

    def _poll_results(self) -> None:
        try:
            kind, text = self.results.get_nowait()
        except queue.Empty:
            self.root.after(250, self._poll_results)
            return

        self.refreshing = False
        if kind == "ok":
            self.last_text = text
        self.label.configure(text=text)
        self.root.update_idletasks()
        if self.options.track_codex and not self.options.geometry:
            self._track_codex_window()
        self.root.after(self.options.refresh_sec * 1000, self._refresh_async)
        self.root.after(250, self._poll_results)

    def _place_default(self) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        x = max(DEFAULT_MARGIN, self.root.winfo_screenwidth() - width - DEFAULT_MARGIN)
        y = DEFAULT_MARGIN
        self.root.geometry(f"+{x}+{y}")

    def _track_codex_window(self) -> None:
        bounds = _read_codex_window_bounds()
        if bounds is None:
            self._place_default()
            return
        x, y, width, _height = bounds
        self.root.update_idletasks()
        overlay_width = self.root.winfo_reqwidth()
        overlay_x = max(DEFAULT_MARGIN, x + width - overlay_width - DEFAULT_MARGIN)
        overlay_y = max(DEFAULT_MARGIN, y + DEFAULT_MARGIN)
        self.root.geometry(f"+{overlay_x}+{overlay_y}")


def _read_overlay_text(
    *,
    mode: str,
    codex_bin: str | None,
    settings: dict[str, Any],
    debug,
) -> str:
    snapshot = datetime.now(timezone.utc)
    response = _read_rate_limits(codex_bin, debug=debug)
    state = build_codex_limit_state(response, snapshot_at=snapshot, debug=debug)
    _augment_reset_bank(state, settings=settings, snapshot=snapshot, debug=debug)
    if mode == "pill":
        return render_pill(state, settings=settings)
    return render_expanded(state, settings=settings)


def _read_codex_window_bounds() -> tuple[int, int, int, int] | None:
    if platform.system() != "Darwin":
        return None
    script = """
tell application "System Events"
  if not (exists process "Codex") then return ""
  tell process "Codex"
    if not (exists window 1) then return ""
    set windowPosition to position of window 1
    set windowSize to size of window 1
    set boundsText to item 1 of windowPosition as text
    set boundsText to boundsText & "," & item 2 of windowPosition as text
    set boundsText to boundsText & "," & item 1 of windowSize as text
    set boundsText to boundsText & "," & item 2 of windowSize as text
    return boundsText
  end tell
end tell
""".strip()
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    if not text:
        return None
    try:
        x, y, width, height = [int(part.strip()) for part in text.split(",")]
    except ValueError:
        return None
    return x, y, width, height


def _error_text(exc: Exception) -> str:
    message = str(exc).splitlines()[0].strip()
    if not message:
        message = exc.__class__.__name__
    if len(message) > 160:
        message = message[:157] + "..."
    return f"Codex limits unavailable\n{message}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show Codex limits in a small always-on-top overlay.")
    parser.add_argument(
        "--mode",
        choices=("pill", "expanded"),
        default="pill",
        help="Overlay text mode. Defaults to pill.",
    )
    parser.add_argument(
        "--refresh-sec",
        type=int,
        default=DEFAULT_REFRESH_SECONDS,
        help="Refresh interval in seconds. Values below 10 are clamped to 10.",
    )
    parser.add_argument("--codex-bin", help="Path to codex binary. Defaults to PATH or CODEX_BIN.")
    parser.add_argument("--settings", help="Optional settings.json path.")
    parser.add_argument("--debug-log", help="Write reset bank raw shape diagnostics to this file.")
    parser.add_argument(
        "--geometry",
        help='Tk geometry override, for example "+1200+20". Disables automatic Codex tracking.',
    )
    parser.add_argument(
        "--no-track-codex",
        action="store_true",
        help="Do not try to attach the overlay near the Codex window.",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        default=0.9,
        help="Overlay opacity from 0.2 to 1.0.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
