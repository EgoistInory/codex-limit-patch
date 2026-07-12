# Milestone 1 Demo

This demo validates the provider-neutral data contract and alert behavior for
Codex, Claude Code, DeepSeek, GLM, and Xiaomi MiMo.

All values in `snapshots.json` are synthetic. They do not represent live
provider support, real accounts, credentials, prices, or current plan limits.
The different shapes are intentional:

- Codex and Claude Code use subscription quota windows.
- DeepSeek exposes a currency balance without a fake percentage.
- GLM uses an explicitly estimated local token package.
- Xiaomi MiMo remains unavailable when no trustworthy source is configured.

Generate the deterministic browser payload:

```bash
python3 -m codex_limit_patch.usage_monitor.demo \
  --input demos/milestone-1/snapshots.json \
  --output demos/milestone-1/demo-data.js \
  --now 2026-07-11T03:00:00Z
```

Then open `index.html` directly. The dashboard has no runtime dependencies and
does not start a server or read local credentials.
