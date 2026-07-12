# Milestone 3: Live Codex and Claude Code

This milestone adds safe local Claude Code usage accounting beside the live
Codex quota source.

- Codex: live subscription windows and reset credits from the local app-server.
- Claude Code: live local request and token totals from allowlisted project
  JSONL logs.
- DeepSeek, GLM, and Xiaomi MiMo: synthetic rows visibly marked `Demo`.

The Claude scanner reads only assistant timestamps, message IDs for
deduplication, model IDs, and numeric usage fields. It does not retain prompts,
responses, tool content, working directories, settings, credentials, or account
identity. Local Claude usage is not an official subscription quota.

Generate the ignored local payload:

```bash
python3 -m codex_limit_patch.usage_monitor.multi_live_demo
```

Then open `index-live.html`. The committed `index.html` remains a synthetic,
credential-free example.
