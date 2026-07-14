# Milestone 4: Expanded Live Providers

This milestone combines local client usage and read-only official quota APIs.

- Codex: subscription windows and reset credits from the local app-server.
- Claude Code: request and token totals from allowlisted local JSONL fields.
- Gemini CLI: today's request and token totals from allowlisted local JSONL
  fields. Subscription limits and OAuth credentials are deliberately excluded.
- DeepSeek: CNY/USD balance with granted and paid components from the official
  `GET /user/balance` API.
- Kimi Code: rolling and weekly request limits from its official usage API.
- Zhipu GLM: Coding Plan token and MCP/time quotas from its official quota API.
- MiniMax: rolling and weekly Token Plan limits from its official API.
- Xiaomi MiMo: reserved Demo row for a later provider adapter.

The monitor only displays usage and availability. It does not configure,
switch, or proxy model providers. API credentials are read from environment
variables, kept in memory, and never written to the generated payload. Without
a key, the corresponding row remains visibly **Not configured**.

For daily use on macOS, install and start the menu-bar companion once:

```bash
pip install -e '.[macos-menubar]'
ai_usage_monitor_menubar
```

It refreshes all sources every 60 seconds, displays compact provider values and
alerts in the system menu bar, and keeps the ignored `demo-data.js` current.
Use **Open Dashboard** only when the full detail view is needed. An already-open
live dashboard reloads every 60 seconds.

The one-shot snapshot command remains available for diagnostics:

```bash
python3 -m codex_limit_patch.usage_monitor.three_source_demo
```

Alternate environment variables can be selected without putting keys on the
command line:

```bash
ai_usage_monitor_demo \
  --deepseek-api-key-env MY_DEEPSEEK_KEY \
  --kimi-api-key-env MY_KIMI_KEY \
  --zhipu-api-key-env MY_GLM_KEY \
  --minimax-api-key-env MY_MINIMAX_KEY
```

The committed `index.html` is a credential-free example with synthetic values.
