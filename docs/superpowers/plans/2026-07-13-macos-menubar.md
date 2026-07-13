# macOS Menu Bar Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native macOS menu-bar companion that automatically refreshes the existing Codex, Claude Code, and DeepSeek usage data.

**Architecture:** Extract a shared collection pass from the Milestone 4 CLI, format the normalized payload through a GUI-independent presentation model, and keep the optional `rumps` adapter thin. Provider work runs off the AppKit main loop and each successful refresh updates both the menu and the existing dashboard snapshot.

**Tech Stack:** Python 3.8+, standard library threading/queue/webbrowser, optional rumps 0.x, existing HTML/CSS/JavaScript dashboard.

## Global Constraints

- Preserve every existing CLI and overlay behavior.
- Do not add provider configuration, model switching, proxying, or credential persistence.
- Keep the menu-bar dependency optional and macOS-only at runtime.
- Keep provider reads off the UI thread and suppress concurrent refreshes.
- Use the existing normalized payload and alert contracts.

---

### Task 1: Shared Three-Provider Collector

**Files:**
- Create: `codex_limit_patch/usage_monitor/collector.py`
- Modify: `codex_limit_patch/usage_monitor/three_source_demo.py`
- Test: `tests/test_usage_monitor_collector.py`

**Interfaces:**
- Produces: `collect_three_source_payload(fixture_path, codex_bin=None, claude_config_dir=None, deepseek_api_key=None, deepseek_environ=None, now=None, codex_fetcher=fetch_codex_outcome, claude_fetcher=fetch_claude_outcome, deepseek_fetcher=fetch_deepseek_outcome) -> dict`
- Consumes: existing `fetch_codex_outcome`, `fetch_claude_outcome`, `fetch_deepseek_outcome`, and `build_three_source_payload`.

- [ ] Write tests with injected fetch functions proving provider order, options, and one shared timestamp.
- [ ] Run the targeted test and confirm the collector import or behavior fails.
- [ ] Implement the collector and change the CLI to call it.
- [ ] Run collector and three-source CLI tests until green.

### Task 2: Menu Presentation Model

**Files:**
- Create: `codex_limit_patch/usage_monitor/menubar_model.py`
- Test: `tests/test_usage_monitor_menubar_model.py`

**Interfaces:**
- Produces: immutable `MenuPresentation(title, rows, updated_label, error_message)` and `build_menu_presentation(payload, error_message=None)`.
- Menu rows expose provider id, label, detail, status, and source label.

- [ ] Write failing tests for healthy, warning, unavailable, quota-percent, token-total, and currency-balance formatting.
- [ ] Run the targeted tests and confirm the model is missing.
- [ ] Implement deterministic formatting without importing rumps.
- [ ] Run the targeted tests until green.

### Task 3: Optional macOS Runtime

**Files:**
- Create: `codex_limit_patch/usage_monitor/macos_menubar.py`
- Test: `tests/test_usage_monitor_macos_menubar.py`

**Interfaces:**
- Produces: `MenuBarOptions`, `sanitize_error`, `require_macos`, `main`, and a `UsageMenuBarApp` thin rumps adapter.
- Consumes: the shared collector, menu presentation model, and `write_browser_payload`.

- [ ] Write failing tests for platform/dependency guards, refresh clamping, concurrent-refresh suppression, snapshot writes, and sanitized errors using a fake rumps module.
- [ ] Run the targeted tests and confirm the runtime is missing.
- [ ] Implement worker-thread collection, main-loop result application, Refresh Now, Open Dashboard, and Quit.
- [ ] Run the targeted tests until green.

### Task 4: Packaging And Live Dashboard Handoff

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_cli_entrypoint.py`
- Modify: `demos/milestone-4/index-live.html`
- Modify: `demos/milestone-4/README.md`
- Modify: `README.md`
- Modify: `README_zh.md`

**Interfaces:**
- Produces command `ai_usage_monitor_menubar` and optional extra `macos-menubar`.

- [ ] Add failing package-metadata and live-page tests for the new command, optional dependency, and 60-second reload.
- [ ] Run those tests and confirm they fail.
- [ ] Add the optional dependency, entry point, live-page reload, and concise operating instructions.
- [ ] Run metadata and Demo tests until green.

### Task 5: End-To-End Verification

**Files:**
- No tracked production changes expected.

- [ ] Run `python3 -m unittest discover -s tests -v` and require all tests to pass.
- [ ] Run `python3 -m compileall -q codex_limit_patch` and JavaScript syntax checks.
- [ ] Install `.[macos-menubar]` in the project environment without modifying tracked egg-info files.
- [ ] Launch `ai_usage_monitor_menubar`, confirm it remains alive, and verify it writes a fresh ignored Milestone 4 payload.
- [ ] Scan the generated payload for keys, authorization headers, cookies, prompts, and working-directory fields.
- [ ] Review the final diff without staging the pre-existing `codex_limit_patch.egg-info` changes.
