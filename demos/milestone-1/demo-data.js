window.USAGE_MONITOR_DEMO = {
  "schema_version": 1,
  "demo": true,
  "generated_at": "2026-07-11T03:00:00Z",
  "accounts": [
    {
      "id": "openai-codex-plus",
      "provider_id": "openai",
      "provider_name": "OpenAI",
      "account_kind": "subscription",
      "status": "available",
      "source_type": "local_client",
      "source_label": "Codex app-server demo",
      "fetched_at": "2026-07-11T03:00:00Z",
      "stale_after_seconds": 300,
      "client_name": "Codex",
      "quotas": [
        {
          "id": "five-hour",
          "label": "5-hour window",
          "unit": "percent",
          "used": 65,
          "limit": 100,
          "remaining": 35,
          "remaining_percent": 35,
          "resets_at": "2026-07-11T05:20:00Z",
          "period_label": "5 hours",
          "accuracy": "exact"
        },
        {
          "id": "weekly",
          "label": "Weekly window",
          "unit": "percent",
          "used": 86,
          "limit": 100,
          "remaining": 14,
          "remaining_percent": 14,
          "resets_at": "2026-07-15T08:00:00Z",
          "period_label": "7 days",
          "accuracy": "exact"
        }
      ],
      "models": [
        {
          "model_id": "gpt-5-codex",
          "display_name": "GPT-5 Codex",
          "input_tokens": 532400,
          "output_tokens": 151800,
          "cost": null,
          "currency": null
        }
      ],
      "requests_today": 87,
      "tokens_today": 684200,
      "cost_today": null,
      "currency": null,
      "message": null
    },
    {
      "id": "anthropic-claude-max",
      "provider_id": "anthropic",
      "provider_name": "Anthropic",
      "account_kind": "subscription",
      "status": "available",
      "source_type": "oauth_usage",
      "source_label": "Claude usage demo",
      "fetched_at": "2026-07-11T03:00:00Z",
      "stale_after_seconds": 300,
      "client_name": "Claude Code",
      "quotas": [
        {
          "id": "five-hour",
          "label": "Session window",
          "unit": "percent",
          "used": 92,
          "limit": 100,
          "remaining": 8,
          "remaining_percent": 8,
          "resets_at": "2026-07-11T04:40:00Z",
          "period_label": "5 hours",
          "accuracy": "exact"
        },
        {
          "id": "weekly",
          "label": "Weekly window",
          "unit": "percent",
          "used": 48,
          "limit": 100,
          "remaining": 52,
          "remaining_percent": 52,
          "resets_at": "2026-07-16T00:00:00Z",
          "period_label": "7 days",
          "accuracy": "exact"
        }
      ],
      "models": [
        {
          "model_id": "claude-opus",
          "display_name": "Claude Opus",
          "input_tokens": 702100,
          "output_tokens": 219400,
          "cost": null,
          "currency": null
        }
      ],
      "requests_today": 114,
      "tokens_today": 921500,
      "cost_today": null,
      "currency": null,
      "message": null
    },
    {
      "id": "deepseek-api-main",
      "provider_id": "deepseek",
      "provider_name": "DeepSeek",
      "account_kind": "api",
      "status": "available",
      "source_type": "official_api",
      "source_label": "Balance API demo",
      "fetched_at": "2026-07-11T02:58:00Z",
      "stale_after_seconds": 900,
      "client_name": null,
      "quotas": [
        {
          "id": "balance",
          "label": "API balance",
          "unit": "CNY",
          "used": null,
          "limit": null,
          "remaining": 42.6,
          "remaining_percent": null,
          "resets_at": null,
          "period_label": null,
          "accuracy": "exact"
        }
      ],
      "models": [
        {
          "model_id": "deepseek-chat",
          "display_name": "DeepSeek Chat",
          "input_tokens": 1980400,
          "output_tokens": 500200,
          "cost": 3.86,
          "currency": "CNY"
        }
      ],
      "requests_today": 462,
      "tokens_today": 2480600,
      "cost_today": 3.86,
      "currency": "CNY",
      "message": null
    },
    {
      "id": "zhipu-glm-coding-plan",
      "provider_id": "zhipu",
      "provider_name": "Zhipu AI",
      "account_kind": "local_estimate",
      "status": "available",
      "source_type": "local_logs",
      "source_label": "Local token estimate",
      "fetched_at": "2026-07-11T02:55:00Z",
      "stale_after_seconds": 1800,
      "client_name": "GLM Coding Plan",
      "quotas": [
        {
          "id": "token-package",
          "label": "Token package",
          "unit": "tokens",
          "used": 820000,
          "limit": 1000000,
          "remaining": 180000,
          "remaining_percent": 18,
          "resets_at": "2026-07-12T00:00:00Z",
          "period_label": "Daily estimate",
          "accuracy": "estimated"
        }
      ],
      "models": [
        {
          "model_id": "glm-coding",
          "display_name": "GLM Coding",
          "input_tokens": 651000,
          "output_tokens": 169000,
          "cost": null,
          "currency": null
        }
      ],
      "requests_today": 238,
      "tokens_today": 820000,
      "cost_today": null,
      "currency": null,
      "message": null
    },
    {
      "id": "xiaomi-mimo-main",
      "provider_id": "xiaomi",
      "provider_name": "Xiaomi MiMo",
      "account_kind": "api",
      "status": "unavailable",
      "source_type": "official_api",
      "source_label": "MiMo console session",
      "fetched_at": "2026-07-11T03:00:00Z",
      "stale_after_seconds": 900,
      "client_name": null,
      "quotas": [
        {
          "id": "balance",
          "label": "Platform balance",
          "unit": "CNY",
          "used": null,
          "limit": null,
          "remaining": null,
          "remaining_percent": null,
          "resets_at": null,
          "period_label": null,
          "accuracy": "unavailable"
        }
      ],
      "models": [],
      "requests_today": null,
      "tokens_today": null,
      "cost_today": null,
      "currency": null,
      "message": "No read-only MiMo usage source is configured for this demo."
    }
  ],
  "alerts": [
    {
      "account_id": "anthropic-claude-max",
      "kind": "quota",
      "severity": "critical",
      "title": "Anthropic quota is low",
      "message": "Session window has 8% remaining.",
      "quota_id": "five-hour"
    },
    {
      "account_id": "xiaomi-mimo-main",
      "kind": "unavailable",
      "severity": "critical",
      "title": "Xiaomi MiMo is unavailable",
      "message": "No read-only MiMo usage source is configured for this demo.",
      "quota_id": null
    },
    {
      "account_id": "openai-codex-plus",
      "kind": "quota",
      "severity": "warning",
      "title": "OpenAI quota is low",
      "message": "Weekly window has 14% remaining.",
      "quota_id": "weekly"
    },
    {
      "account_id": "zhipu-glm-coding-plan",
      "kind": "quota",
      "severity": "warning",
      "title": "Zhipu AI quota is low",
      "message": "Token package has 18% remaining.",
      "quota_id": "token-package"
    }
  ]
};
