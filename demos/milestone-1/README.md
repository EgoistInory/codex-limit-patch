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

The visual dashboard will be available at `index.html` when this milestone is
complete. It can be opened directly without installing dependencies.
