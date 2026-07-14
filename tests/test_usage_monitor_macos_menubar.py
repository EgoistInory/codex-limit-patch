from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_limit_patch.usage_monitor.macos_menubar import (
    MenuBarOptions,
    UsageMenuBarApp,
    require_macos,
    sanitize_error,
)


class FakeMenuItem:
    def __init__(self, title, callback=None):
        self.title = title
        self.callback = callback
        self.children = []

    def add(self, item):
        self.children.append(item)


class FakeApp:
    def __init__(self, name, title, quit_button=None):
        self.name = name
        self.title = title
        self.quit_button = quit_button
        self.menu = []
        self.run_called = False

    def run(self):
        self.run_called = True


class FakeTimer:
    def __init__(self, callback, interval):
        self.callback = callback
        self.interval = interval
        self.started = False

    def start(self):
        self.started = True


class FakeRumps:
    App = FakeApp
    MenuItem = FakeMenuItem
    Timer = FakeTimer

    def __init__(self):
        self.quit_called = False

    def quit_application(self):
        self.quit_called = True


class ImmediateThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


class DeferredThread(ImmediateThread):
    starts = 0

    def start(self):
        type(self).starts += 1


def payload():
    return {
        "generated_at": "2026-07-13T02:00:00Z",
        "live_provider_ids": ["openai", "anthropic", "deepseek"],
        "accounts": [
            {
                "id": "openai-live",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "status": "available",
                "source_label": "Codex app-server",
                "quotas": [
                    {
                        "label": "5-hour",
                        "remaining_percent": 78,
                        "remaining": None,
                        "unit": "percent",
                        "resets_at": "2026-07-13T04:30:00Z",
                    }
                ],
            },
            {
                "id": "anthropic-live",
                "provider_id": "anthropic",
                "provider_name": "Anthropic",
                "status": "available",
                "source_label": "Claude Code local logs",
                "tokens_today": 1200,
                "quotas": [],
            },
            {
                "id": "deepseek-live",
                "provider_id": "deepseek",
                "provider_name": "DeepSeek",
                "status": "unavailable",
                "source_label": "No successful source",
                "quotas": [],
            },
        ],
        "alerts": [
            {
                "account_id": "deepseek-live",
                "kind": "unavailable",
                "severity": "critical",
            }
        ],
        "fetch_attempts": {
            "deepseek": [
                {
                    "strategy_id": "balance-api",
                    "available": False,
                    "success": False,
                }
            ]
        },
    }


class MacOSMenuBarTests(unittest.TestCase):
    def test_platform_guard_and_error_sanitizer(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "macOS"):
            require_macos("Linux")
        require_macos("Darwin")
        self.assertEqual(sanitize_error(RuntimeError("first line\nsecret")), "first line")
        sanitized = sanitize_error(
            RuntimeError("request failed: Bearer abc123 and sk-sensitive-value")
        )
        self.assertNotIn("abc123", sanitized)
        self.assertNotIn("sk-sensitive-value", sanitized)
        self.assertLessEqual(len(sanitize_error(RuntimeError("x" * 500))), 160)

    def test_options_clamp_refresh_interval(self) -> None:
        options = MenuBarOptions(refresh_sec=2)

        self.assertEqual(options.refresh_sec, 15)

    def test_refresh_updates_menu_and_writes_browser_snapshot(self) -> None:
        fake_rumps = FakeRumps()
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "demo-data.js"
            options = MenuBarOptions(refresh_sec=60, output_path=output)
            app = UsageMenuBarApp(
                options,
                rumps_module=fake_rumps,
                collector=lambda **kwargs: calls.append(kwargs) or payload(),
                thread_factory=ImmediateThread,
            )

            app.schedule_refresh()
            app.poll_results()

            self.assertEqual(len(calls), 1)
            self.assertEqual(app.app.title, "AI · OK")
            self.assertIn("OpenAI · 5-hour 78%", app.provider_items["openai"].title)
            self.assertIn("Source · Codex app-server", app.source_items["openai"].title)
            self.assertIn("Resets · 5-hour", app.reset_items["openai"].title)
            self.assertIn("DeepSeek · Not configured", app.provider_items["deepseek"].title)
            self.assertEqual(
                app.updated_item.title,
                "Data refreshed · 2026-07-13 02:00 UTC",
            )
            self.assertTrue(output.exists())
            text = output.read_text(encoding="utf-8")
            decoded = json.loads(text[len("window.USAGE_MONITOR_DEMO = ") : -2])
            self.assertEqual(decoded["live_provider_ids"], ["openai", "anthropic", "deepseek"])

    def test_concurrent_refresh_is_suppressed(self) -> None:
        DeferredThread.starts = 0
        app = UsageMenuBarApp(
            MenuBarOptions(),
            rumps_module=FakeRumps(),
            collector=lambda **_kwargs: payload(),
            thread_factory=DeferredThread,
        )

        app.schedule_refresh()
        app.schedule_refresh()

        self.assertEqual(DeferredThread.starts, 1)
        self.assertTrue(app.refreshing)


if __name__ == "__main__":
    unittest.main()
