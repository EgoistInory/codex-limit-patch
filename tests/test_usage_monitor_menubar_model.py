from __future__ import annotations

import unittest

from codex_limit_patch.usage_monitor.menubar_model import build_menu_presentation


def account(provider_id, name, *, status="available", quotas=None, tokens=None, message=None):
    return {
        "id": "%s-main" % provider_id,
        "provider_id": provider_id,
        "provider_name": name,
        "status": status,
        "source_label": "%s source" % name,
        "tokens_today": tokens,
        "message": message,
        "quotas": quotas or [],
    }


class MenuBarModelTests(unittest.TestCase):
    def test_formats_provider_specific_rows_and_healthy_title(self) -> None:
        payload = {
            "generated_at": "2026-07-13T02:00:00Z",
            "accounts": [
                account(
                    "openai",
                    "OpenAI",
                    quotas=[
                        {"label": "5-hour", "remaining_percent": 78, "remaining": None, "unit": "percent"},
                        {"label": "Weekly", "remaining_percent": 64, "remaining": None, "unit": "percent"},
                    ],
                ),
                account("anthropic", "Anthropic", tokens=1250000),
                account(
                    "deepseek",
                    "DeepSeek",
                    quotas=[
                        {"label": "CNY API balance", "remaining_percent": None, "remaining": 42.6, "unit": "CNY"}
                    ],
                ),
            ],
            "alerts": [],
        }

        presentation = build_menu_presentation(payload)

        self.assertEqual(presentation.title, "AI ✓")
        self.assertEqual([row.provider_id for row in presentation.rows], ["openai", "anthropic", "deepseek"])
        self.assertEqual(presentation.rows[0].detail, "5-hour 78% · Weekly 64%")
        self.assertEqual(presentation.rows[1].detail, "1.2M tokens today")
        self.assertEqual(presentation.rows[2].detail, "42.6 CNY")
        self.assertEqual(presentation.updated_label, "Updated 2026-07-13 02:00 UTC")

    def test_critical_alerts_and_unavailable_provider_are_explicit(self) -> None:
        payload = {
            "generated_at": "2026-07-13T02:00:00Z",
            "accounts": [
                account(
                    "deepseek",
                    "DeepSeek",
                    status="unavailable",
                    message="API key is not configured.",
                )
            ],
            "alerts": [{"severity": "critical"}, {"severity": "warning"}],
        }

        presentation = build_menu_presentation(payload)

        self.assertEqual(presentation.title, "AI !1")
        self.assertEqual(presentation.rows[0].detail, "Unavailable")
        self.assertEqual(presentation.rows[0].status, "unavailable")
        self.assertEqual(presentation.rows[0].source_label, "DeepSeek source")

    def test_collection_error_takes_precedence_without_discarding_rows(self) -> None:
        payload = {
            "generated_at": "2026-07-13T02:00:00Z",
            "accounts": [account("anthropic", "Anthropic", tokens=500)],
            "alerts": [],
        }

        presentation = build_menu_presentation(payload, error_message="Refresh failed")

        self.assertEqual(presentation.title, "AI ×")
        self.assertEqual(presentation.error_message, "Refresh failed")
        self.assertEqual(len(presentation.rows), 1)

    def test_excludes_demo_only_accounts_from_live_menu(self) -> None:
        payload = {
            "generated_at": "2026-07-13T02:00:00Z",
            "live_provider_ids": ["openai", "anthropic", "deepseek"],
            "accounts": [
                account("openai", "OpenAI"),
                account("anthropic", "Anthropic"),
                account("deepseek", "DeepSeek"),
                account("zhipu", "Zhipu AI"),
                account("xiaomi", "Xiaomi MiMo"),
            ],
            "alerts": [],
        }

        presentation = build_menu_presentation(payload)

        self.assertEqual(
            [row.provider_id for row in presentation.rows],
            ["openai", "anthropic", "deepseek"],
        )

    def test_excludes_demo_account_alerts_from_menu_title(self) -> None:
        payload = {
            "generated_at": "2026-07-13T02:00:00Z",
            "live_provider_ids": ["openai"],
            "accounts": [
                account("openai", "OpenAI"),
                account("xiaomi", "Xiaomi MiMo", status="unavailable"),
            ],
            "alerts": [
                {
                    "account_id": "xiaomi-main",
                    "severity": "critical",
                }
            ],
        }

        presentation = build_menu_presentation(payload)

        self.assertEqual(presentation.title, "AI ✓")


if __name__ == "__main__":
    unittest.main()
