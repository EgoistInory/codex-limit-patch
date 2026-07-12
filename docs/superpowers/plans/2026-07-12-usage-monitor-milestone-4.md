# Usage Monitor Milestone 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add official DeepSeek API balance monitoring, including paid/granted breakdowns and degraded availability alerts, then preserve a three-source dashboard demo.

**Architecture:** Extend quota windows with typed metric components so balances can retain their official breakdown without provider-specific UI fields. A DeepSeek strategy resolves an opt-in API key from explicit input or environment, calls the official HTTPS balance endpoint through a bounded standard-library client, and maps every returned currency into a normalized balance quota. The multi-source demo reuses the existing outcome compositor.

**Tech Stack:** Python 3.8+ standard library (`urllib`, `json`, `decimal`), `unittest`, existing provider runner and dashboard.

## Global Constraints

- Use only the official `GET https://api.deepseek.com/user/balance` endpoint.
- Read API keys only from explicit constructor input, `DEEPSEEK_API_KEY`, or `DEEPSEEK_KEY`.
- Never persist, serialize, log, or include keys in errors or debug output.
- Enforce HTTPS, a 10-second timeout, and a 1 MiB response limit.
- Do not invent session, weekly, monthly, or percentage quotas for DeepSeek.
- Keep Codex, Claude, and all earlier demos unchanged.
- Add no third-party runtime dependency.

---

### Task 1: Balance Components and Degraded Alerts

**Files:**
- Modify: `codex_limit_patch/usage_monitor/models.py`
- Modify: `codex_limit_patch/usage_monitor/alerts.py`
- Modify: `demos/milestone-1/dashboard.js`
- Test: `tests/test_usage_monitor_models.py`
- Test: `tests/test_usage_monitor_alerts.py`

**Interfaces:**
- Produces: `MetricComponent(label, value, unit)` and `QuotaWindow.components`.
- Extends: `evaluate_alerts` with a warning for `snapshot.status == "degraded"`.

- [ ] **Step 1: Write failing round-trip and alert tests**

```python
def test_balance_components_round_trip():
    quota = QuotaWindow.from_dict({"id": "balance-cny", "label": "Balance", "unit": "CNY", "components": [{"label": "Granted", "value": 10, "unit": "CNY"}]})
    self.assertEqual(quota.components[0].value, 10)


def test_degraded_snapshot_emits_availability_warning():
    alerts = evaluate_alerts(make_snapshot(status="degraded"), now=NOW)
    self.assertTrue(any(item.kind == "availability" for item in alerts))
```

- [ ] **Step 2: Verify RED, implement, and verify GREEN**

Run: `python3 -m unittest tests.test_usage_monitor_models tests.test_usage_monitor_alerts -v`

Expected before implementation: FAIL. Expected after implementation: PASS.

- [ ] **Step 3: Render balance components through text-only DOM APIs**

Display components below a quota track as compact `Paid` / `Granted` values. Preserve unknown values and never inject HTML.

- [ ] **Step 4: Run full tests and commit**

```bash
python3 -m unittest discover -s tests
node --check demos/milestone-1/dashboard.js
git add codex_limit_patch/usage_monitor/models.py codex_limit_patch/usage_monitor/alerts.py demos/milestone-1/dashboard.js tests/test_usage_monitor_models.py tests/test_usage_monitor_alerts.py
git commit -m "Add balance breakdown and degraded alerts"
```

### Task 2: DeepSeek Official Balance Provider

**Files:**
- Create: `codex_limit_patch/usage_monitor/providers/deepseek.py`
- Modify: `codex_limit_patch/usage_monitor/providers/__init__.py`
- Test: `tests/test_usage_monitor_deepseek_provider.py`

**Interfaces:**
- Produces: `DeepSeekBalanceClient.fetch(api_key)`, `parse_deepseek_balance(payload, now)`, `DeepSeekBalanceStrategy`, and `fetch_deepseek_outcome(api_key=None, now=None)`.

- [ ] **Step 1: Write failing parser, strategy, and client tests**

Test CNY/USD mapping, paid/granted components, `is_available == false`, missing API key, invalid decimal strings, HTTPS enforcement, authorization header construction through an injected opener, response size limit, and absence of key text in snapshots/errors.

- [ ] **Step 2: Verify RED and implement the bounded client/parser**

Run: `python3 -m unittest tests.test_usage_monitor_deepseek_provider -v`

Expected before implementation: FAIL. Expected after implementation: PASS.

- [ ] **Step 3: Run full tests and commit**

```bash
python3 -m unittest discover -s tests
python3 -m py_compile codex_limit_patch/usage_monitor/providers/*.py
git add codex_limit_patch/usage_monitor/providers tests/test_usage_monitor_deepseek_provider.py
git commit -m "Add DeepSeek balance provider"
```

### Task 3: Three-Source Milestone 4 Demo

**Files:**
- Create: `codex_limit_patch/usage_monitor/three_source_demo.py`
- Create: `demos/milestone-4/index.html`
- Create: `demos/milestone-4/index-live.html`
- Create: `demos/milestone-4/demo-data.example.js`
- Create: `demos/milestone-4/README.md`
- Modify: `.gitignore`
- Test: `tests/test_usage_monitor_three_source_demo.py`

**Interfaces:**
- Consumes: Codex, Claude, and DeepSeek outcomes.
- Produces: an ignored local payload with `live_provider_ids == ["openai", "anthropic", "deepseek"]`.

- [ ] **Step 1: Write failing composition and asset tests**

Verify the three provider rows are non-demo, GLM/MiMo remain demo, provider order is stable, missing DeepSeek key becomes an explicit unavailable live row, and example/live entrypoints exist.

- [ ] **Step 2: Implement CLI and preserved Demo**

The CLI accepts `--deepseek-api-key-env` only as an environment variable name override, never a literal key argument. Default resolution remains `DEEPSEEK_API_KEY` then `DEEPSEEK_KEY`.

- [ ] **Step 3: Verify and commit**

```bash
python3 -m unittest discover -s tests
python3 -m codex_limit_patch.usage_monitor.three_source_demo --output /tmp/codex-limit-monitor-m4.js
git add .gitignore codex_limit_patch/usage_monitor/three_source_demo.py demos/milestone-4 tests/test_usage_monitor_three_source_demo.py
git commit -m "Add DeepSeek balance dashboard demo"
```
