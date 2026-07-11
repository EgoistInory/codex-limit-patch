# Usage Monitor Milestone 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe local Claude Code token accounting and preserve a mixed dashboard demo with live Codex and live Claude Code rows.

**Architecture:** A focused JSONL scanner reads only `projects/**/*.jsonl` under the resolved Claude config directory, extracts assistant usage fields, deduplicates message IDs, and returns aggregate model totals. A Claude provider strategy maps those totals into the neutral snapshot contract without inventing subscription quotas. The mixed demo replaces both OpenAI and Anthropic fixture rows while keeping remaining providers visibly synthetic.

**Tech Stack:** Python 3.8+ standard library, `unittest`, existing provider runner and dashboard.

## Global Constraints

- Do not read Claude credentials, Keychain, settings, history, prompts, tool content, or message text.
- Scan only JSONL files under the allowlisted Claude `projects` directory.
- Retain only timestamps, model IDs, message IDs for deduplication, and numeric usage fields in memory.
- Label Claude data `local_logs` and `local_estimate`; do not expose subscription percentages or reset times.
- Preserve the existing Codex CLI, parser, overlay, and Milestone 1/2 demos.
- Add no third-party runtime dependency.

---

### Task 1: Claude Local Usage Scanner

**Files:**
- Modify: `codex_limit_patch/usage_monitor/models.py`
- Create: `codex_limit_patch/usage_monitor/claude_logs.py`
- Test: `tests/test_usage_monitor_claude_logs.py`
- Modify: `tests/test_usage_monitor_models.py`

**Interfaces:**
- Produces: `ClaudeModelTotals`, `ClaudeUsageTotals`, `parse_claude_log_lines(lines, start, end, seen_ids=None)`, and `scan_claude_projects(projects_dir, start, end)`.
- Extends: `ModelUsage` with optional `cache_read_tokens` and `cache_creation_tokens`.

- [ ] **Step 1: Write failing parser tests**

```python
def test_parser_counts_assistant_usage_and_cache_tokens():
    totals = parse_claude_log_lines(LINES, start=START, end=END)
    self.assertEqual(totals.requests, 1)
    self.assertEqual(totals.input_tokens, 100)
    self.assertEqual(totals.cache_read_tokens, 400)
    self.assertEqual(totals.total_tokens, 570)


def test_parser_ignores_message_text_and_deduplicates_message_id():
    totals = parse_claude_log_lines([LINE, LINE], start=START, end=END)
    self.assertEqual(totals.requests, 1)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_claude_logs -v`

Expected: FAIL because `claude_logs.py` does not exist.

- [ ] **Step 3: Implement line parsing and aggregate dataclasses**

Parse each line with `json.loads`, require `type == "assistant"`, a valid timestamp inside `[start, end)`, and an object at `message.usage`. Accept only non-negative integer token fields. Aggregate by `message.model` and deduplicate non-empty `message.id` values. Malformed and unrelated rows increment diagnostics but never abort the scan.

- [ ] **Step 4: Implement allowlisted project scanning**

Resolve the `projects` root, enumerate `.jsonl` files beneath it, skip symlinks and paths escaping the root, and read files line-by-line. Skip files whose modification time predates the period start. Catch per-file `OSError` and return the count in diagnostics.

- [ ] **Step 5: Extend model serialization and run tests**

Run: `python3 -m unittest tests.test_usage_monitor_claude_logs tests.test_usage_monitor_models -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add codex_limit_patch/usage_monitor/models.py codex_limit_patch/usage_monitor/claude_logs.py tests/test_usage_monitor_claude_logs.py tests/test_usage_monitor_models.py
git commit -m "Add safe Claude Code usage scanner"
```

### Task 2: Claude Code Provider Strategy

**Files:**
- Create: `codex_limit_patch/usage_monitor/providers/claude.py`
- Modify: `codex_limit_patch/usage_monitor/providers/__init__.py`
- Test: `tests/test_usage_monitor_claude_provider.py`

**Interfaces:**
- Consumes: `scan_claude_projects` and `CLAUDE_CONFIG_DIR` or `~/.claude/projects`.
- Produces: `ClaudeLocalLogsStrategy.fetch(now) -> AccountSnapshot` and `fetch_claude_outcome(config_dir=None, now=None) -> ProviderFetchOutcome`.

- [ ] **Step 1: Write failing provider tests**

```python
def test_provider_maps_local_totals_without_quota_windows():
    snapshot = ClaudeLocalLogsStrategy(projects_dir=PROJECTS, scanner=fake_scan).fetch(NOW)
    self.assertEqual(snapshot.provider_id, "anthropic")
    self.assertEqual(snapshot.tokens_today, 570)
    self.assertEqual(snapshot.quotas, ())
    self.assertIn("subscription limits", snapshot.message)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_claude_provider -v`

Expected: FAIL because the Claude provider does not exist.

- [ ] **Step 3: Implement local-day boundaries and provider mapping**

Compute local midnight from `now.astimezone()`, scan to `now`, and map aggregate model totals into `ModelUsage`. Use provider id `anthropic`, account id `anthropic-claude-code`, client `Claude Code`, account kind `local_estimate`, source label `Claude Code local logs`, and a 15-minute freshness policy.

- [ ] **Step 4: Verify provider and full tests**

Run: `python3 -m unittest tests.test_usage_monitor_claude_provider -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add codex_limit_patch/usage_monitor/providers tests/test_usage_monitor_claude_provider.py
git commit -m "Add Claude Code local usage provider"
```

### Task 3: Codex and Claude Live Demo

**Files:**
- Create: `codex_limit_patch/usage_monitor/multi_live_demo.py`
- Create: `demos/milestone-3/index.html`
- Create: `demos/milestone-3/index-live.html`
- Create: `demos/milestone-3/demo-data.example.js`
- Create: `demos/milestone-3/README.md`
- Modify: `.gitignore`
- Test: `tests/test_usage_monitor_multi_live_demo.py`

**Interfaces:**
- Consumes: fixture accounts and outcomes from `fetch_codex_outcome` and `fetch_claude_outcome`.
- Produces: a payload with `live_provider_ids == ["openai", "anthropic"]` and a local ignored `demos/milestone-3/demo-data.js`.

- [ ] **Step 1: Write failing composition tests**

```python
def test_multi_live_payload_replaces_openai_and_anthropic_only():
    payload = build_multi_live_payload(FIXTURE, outcomes=OUTCOMES, now=NOW)
    self.assertEqual(payload["live_provider_ids"], ["openai", "anthropic"])
    self.assertFalse(next(item for item in payload["accounts"] if item["provider_id"] == "anthropic")["demo"])
    self.assertTrue(next(item for item in payload["accounts"] if item["provider_id"] == "deepseek")["demo"])
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_multi_live_demo -v`

Expected: FAIL because `multi_live_demo.py` does not exist.

- [ ] **Step 3: Implement multi-outcome composition and CLI**

Replace fixture rows by provider id while preserving row order, evaluate alerts globally, include sanitized attempts per provider, and write the same browser assignment used by earlier demos. The CLI accepts `--claude-config-dir`, `--codex-bin`, `--fixture`, and `--output`.

- [ ] **Step 4: Add preserved example/live entrypoints and docs**

Reuse Milestone 1 CSS and dashboard JavaScript. The example loads synthetic data; the live entrypoint loads ignored local data and labels Codex and Claude as live while all other rows remain Demo.

- [ ] **Step 5: Verify real local sources**

Run: `python3 -m codex_limit_patch.usage_monitor.multi_live_demo --output /tmp/codex-limit-monitor-m3.js`

Expected: Codex uses `Codex app-server`; Claude uses `Claude Code local logs`; output contains no auth, cookie, prompt, content, cwd, email, or account identity fields.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

Run: `python3 -m py_compile codex_limit_patch/usage_monitor/*.py codex_limit_patch/usage_monitor/providers/*.py`

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add .gitignore codex_limit_patch/usage_monitor/multi_live_demo.py demos/milestone-3 tests/test_usage_monitor_multi_live_demo.py
git commit -m "Add Codex and Claude live usage demo"
```
