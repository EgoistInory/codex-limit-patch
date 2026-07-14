# Expanded Provider Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe read-only Gemini CLI, Kimi Code, Zhipu GLM Coding Plan, and MiniMax Token Plan usage to the existing dashboard and macOS menu bar.

**Architecture:** Each provider follows the existing descriptor/strategy/outcome boundary. Gemini scans official local JSONL session records; the other providers use exact-host HTTPS clients with explicit API keys. A new expanded collector feeds the existing payload builder while historical three-provider functions remain compatible.

**Tech Stack:** Python standard library, `unittest`, `urllib.request`, JSON/JSONL, existing normalized usage models, rumps adapter tests.

## Global Constraints

- Read-only display only; no switching, routing, proxying, or account management.
- Do not import browser cookies or reuse Gemini OAuth credentials.
- Never serialize API keys, authorization headers, prompts, or source file paths.
- Network clients enforce exact HTTPS hosts/paths, ten-second timeouts, and one MiB response limits.
- Preserve existing Codex, Claude Code, DeepSeek behavior and unrelated `egg-info` changes.

---

### Task 1: Gemini CLI Local Usage

**Files:**
- Create: `codex_limit_patch/usage_monitor/gemini_logs.py`
- Create: `codex_limit_patch/usage_monitor/providers/gemini.py`
- Test: `tests/test_usage_monitor_gemini_logs.py`
- Test: `tests/test_usage_monitor_gemini_provider.py`

**Interfaces:**
- Produces: `scan_gemini_sessions(root: Path, start: datetime, end: datetime) -> GeminiUsageTotals`
- Produces: `fetch_gemini_outcome(config_dir=None, now=None, scanner=...) -> ProviderFetchOutcome`

- [ ] Write parser tests using `type="gemini"`, `timestamp`, `model`, and `tokens`; cover date filtering, malformed lines, request totals, and per-model totals.
- [ ] Run `python3 -m unittest tests.test_usage_monitor_gemini_logs`; expect import failure.
- [ ] Implement a non-symlink `session-*.jsonl` scanner rooted below `<gemini-home>/tmp`; return counts only.
- [ ] Write provider tests asserting `provider_id="google"`, `client_name="Gemini CLI"`, local-estimate semantics, and unavailable behavior for a missing directory.
- [ ] Run both Gemini test modules; expect all tests to pass.

### Task 2: Kimi Code Quota Adapter

**Files:**
- Create: `codex_limit_patch/usage_monitor/providers/kimi.py`
- Test: `tests/test_usage_monitor_kimi_provider.py`

**Interfaces:**
- Produces: `parse_kimi_usage(payload, now) -> AccountSnapshot`
- Produces: `fetch_kimi_outcome(api_key=None, now=None, client=None, environ=None) -> ProviderFetchOutcome`

- [ ] Write tests for overall and 300-minute limits, percentages, resets, explicit/missing keys, exact endpoint/header behavior, response bounds, malformed JSON, and secret exclusion.
- [ ] Run `python3 -m unittest tests.test_usage_monitor_kimi_provider`; expect import failure.
- [ ] Implement `GET https://api.kimi.com/coding/v1/usages`, resolving `KIMI_CODE_API_KEY` before `KIMI_API_KEY`.
- [ ] Run the Kimi tests; expect all tests to pass.

### Task 3: Zhipu And MiniMax Quota Adapters

**Files:**
- Create: `codex_limit_patch/usage_monitor/providers/zhipu.py`
- Create: `codex_limit_patch/usage_monitor/providers/minimax.py`
- Test: `tests/test_usage_monitor_zhipu_provider.py`
- Test: `tests/test_usage_monitor_minimax_provider.py`

**Interfaces:**
- Produces: `fetch_zhipu_outcome(...) -> ProviderFetchOutcome`
- Produces: `fetch_minimax_outcome(...) -> ProviderFetchOutcome`

- [ ] Write Zhipu tests for token/time limits, duration units, values, reset epoch milliseconds, plan labels, key handling, endpoint/header behavior, bounds, and secret exclusion.
- [ ] Implement `GET https://open.bigmodel.cn/api/monitor/usage/quota/limit`, resolving `ZHIPU_API_KEY` before `Z_AI_API_KEY`; run its test module to green.
- [ ] Write MiniMax tests for the general lane, rolling/weekly percentages, count fallback, reset epochs, key handling, endpoint/header behavior, bounds, and secret exclusion.
- [ ] Implement `GET https://www.minimax.io/v1/token_plan/remains`, resolving `MINIMAX_CODING_API_KEY` before `MINIMAX_API_KEY`; run its test module to green.

### Task 4: Expanded Collection And Menu Integration

**Files:**
- Modify: `codex_limit_patch/usage_monitor/collector.py`
- Modify: `codex_limit_patch/usage_monitor/three_source_demo.py`
- Modify: `codex_limit_patch/usage_monitor/macos_menubar.py`
- Modify: `tests/test_usage_monitor_collector.py`
- Modify: `tests/test_usage_monitor_three_source_demo.py`
- Modify: `tests/test_usage_monitor_macos_menubar.py`

**Interfaces:**
- Produces: `SUPPORTED_PROVIDER_ORDER`, `build_supported_payload(...)`, and `collect_supported_payload(...)`.
- Preserves: `build_three_source_payload(...)` and `collect_three_source_payload(...)`.

- [ ] Write integration tests for seven-provider order, shared timestamp, secret exclusion, `Not configured` rows, and historical three-provider compatibility.
- [ ] Run the collector, demo, and menu test modules; expect missing expanded interfaces.
- [ ] Add the expanded collector, switch installed demo/menu callers, and add Google, Kimi, Zhipu, and MiniMax menu rows.
- [ ] Re-run the three integration modules; expect all tests to pass.

### Task 5: Documentation And Release Verification

**Files:**
- Modify: `README.md`
- Modify: `README_zh.md`
- Modify: `demos/milestone-4/README.md`

**Interfaces:**
- Documents credentials and exact-quota versus local-estimate semantics.

- [ ] Document the four providers, environment variables, Gemini local-only behavior, and excluded cookie/OAuth paths.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_*.py'`, `python3 -m compileall -q codex_limit_patch`, and `git diff --check`; expect success.
- [ ] Run `ai_usage_monitor_demo`; inspect only normalized statuses/metrics and fetch-attempt booleans, and scan the payload for secret-bearing keys.
- [ ] Run one installed menu process at a 15-second test interval and confirm two different snapshot timestamps.
- [ ] Stage only relevant source/tests/docs, commit, push `main`, and verify remote `HEAD`; exclude `codex_limit_patch.egg-info/*`.
