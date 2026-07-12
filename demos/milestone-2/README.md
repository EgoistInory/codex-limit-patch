# Milestone 2: Live Codex

This milestone connects the existing local Codex app-server reader to the
provider-neutral usage dashboard. It does not read `~/.codex/auth.json` and does
not change Codex, Claude Code, or provider settings.

Two entrypoints are preserved:

- `index.html` is a committed synthetic example and works immediately.
- `index-live.html` reads a local `demo-data.js` containing the current Codex
  quota snapshot. That file is ignored by Git.

Generate the live local payload from the repository root:

```bash
python3 -m codex_limit_patch.usage_monitor.live_demo
```

Then open `demos/milestone-2/index-live.html`. Only the OpenAI/Codex row is
live. Claude Code, DeepSeek, GLM, and Xiaomi MiMo remain synthetic and are
visibly marked `Demo`.

The generated payload contains normalized quota values, reset timestamps,
source labels, and sanitized fetch-attempt diagnostics. It excludes credentials,
raw app-server responses, account IDs, tokens, cookies, and authorization data.
