# Milestone 4: DeepSeek Balance

This milestone adds the official DeepSeek account balance endpoint beside the
existing live Codex and Claude Code sources.

- Codex: subscription windows and reset credits from the local app-server.
- Claude Code: request and token totals from allowlisted local JSONL fields.
- DeepSeek: CNY/USD balance with granted and paid components from the official
  `GET /user/balance` API.
- GLM and Xiaomi MiMo: reserved Demo rows for later provider adapters.

The monitor only displays usage and availability. It does not configure,
switch, or proxy model providers. DeepSeek credentials are read from
`DEEPSEEK_API_KEY` or `DEEPSEEK_KEY`, kept in memory, and never written to the
generated payload. Without a key, the DeepSeek row remains visibly unavailable.

Generate the ignored local payload:

```bash
python3 -m codex_limit_patch.usage_monitor.three_source_demo
```

An alternate environment variable can be selected without putting the key on
the command line:

```bash
ai_usage_monitor_demo --deepseek-api-key-env MY_DEEPSEEK_KEY
```

Then open `index-live.html`. The committed `index.html` is a credential-free
example with synthetic values.
