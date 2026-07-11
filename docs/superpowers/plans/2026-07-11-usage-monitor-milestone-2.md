# Usage Monitor Milestone 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable provider fetch boundary, map the existing Codex app-server response into the neutral snapshot contract, and preserve a runnable dashboard demo that can replace the synthetic Codex row with live local data.

**Architecture:** Provider descriptors declare stable identity and freshness policy. Ordered fetch strategies return normalized snapshots through a runner that records sanitized attempts and creates an explicit unavailable snapshot when no strategy succeeds. The Codex strategy reuses the existing client and parser without modifying their behavior.

**Tech Stack:** Python 3.8+ standard library, `unittest`, existing Codex app-server client, existing Milestone 1 HTML/CSS/JavaScript dashboard.

## Global Constraints

- Do not modify `codex_limit_patch/client.py`, `parser.py`, `cli.py`, `display.py`, or `overlay.py`.
- Do not read `~/.codex/auth.json` or expose account identity, tokens, cookies, or raw responses.
- Keep provider failures timeout-bounded by their existing clients and sanitize error messages.
- Preserve Milestone 1 as a deterministic synthetic demo.
- Keep live Codex output local and do not commit personal quota values.
- Add no third-party runtime dependency.

---

### Task 1: Provider Descriptor and Fetch Runner

**Files:**
- Create: `codex_limit_patch/usage_monitor/providers/__init__.py`
- Create: `codex_limit_patch/usage_monitor/providers/base.py`
- Test: `tests/test_usage_monitor_providers.py`

**Interfaces:**
- Produces: `ProviderDescriptor`, `FetchAttempt`, `ProviderFetchOutcome`, `FetchStrategy`, and `run_provider(descriptor, strategies, now)`.
- Consumes: strategies exposing `id`, `source_type`, `source_label`, `is_available()`, and `fetch(now)`.

- [ ] **Step 1: Write failing runner tests**

```python
def test_runner_falls_back_to_second_available_strategy():
    outcome = run_provider(DESCRIPTOR, [FailingStrategy(), WorkingStrategy()], now=NOW)
    self.assertEqual(outcome.snapshot.source_label, "Working source")
    self.assertEqual([attempt.success for attempt in outcome.attempts], [False, True])


def test_runner_returns_unavailable_snapshot_without_leaking_multiline_error():
    outcome = run_provider(DESCRIPTOR, [SecretFailingStrategy()], now=NOW)
    self.assertEqual(outcome.snapshot.status, "unavailable")
    self.assertNotIn("token=", outcome.snapshot.message)
    self.assertNotIn("\n", outcome.snapshot.message)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_providers -v`

Expected: FAIL because `usage_monitor.providers` does not exist.

- [ ] **Step 3: Implement the descriptor, strategy protocol, runner, and sanitizer**

`ProviderDescriptor` contains `id`, `display_name`, `client_name`, `account_kind`, and `stale_after_seconds`. `run_provider` skips unavailable strategies, records every attempted strategy, stops at the first successful snapshot, and creates an unavailable `AccountSnapshot` when all usable strategies fail. Sanitization keeps only the exception class and first line, removes bearer/token/key assignments, and truncates messages to 160 characters.

- [ ] **Step 4: Verify provider and full tests**

Run: `python3 -m unittest tests.test_usage_monitor_providers -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add codex_limit_patch/usage_monitor/providers tests/test_usage_monitor_providers.py
git commit -m "Add provider fetch strategy runner"
```

### Task 2: Codex App-Server Strategy

**Files:**
- Modify: `codex_limit_patch/usage_monitor/models.py`
- Create: `codex_limit_patch/usage_monitor/providers/codex.py`
- Modify: `codex_limit_patch/usage_monitor/providers/__init__.py`
- Test: `tests/test_usage_monitor_codex_provider.py`
- Modify: `tests/test_usage_monitor_models.py`

**Interfaces:**
- Consumes: `CodexAppServerClient.read_rate_limits()` and `build_codex_limit_state(response, snapshot_at=now, now=now)`.
- Produces: `CodexAppServerStrategy.fetch(now) -> AccountSnapshot` and `fetch_codex_outcome(codex_bin=None, now=None) -> ProviderFetchOutcome`.

- [ ] **Step 1: Write failing mapping tests**

```python
def test_codex_strategy_maps_windows_plan_and_reset_credits():
    snapshot = CodexAppServerStrategy(client=FakeClient(RESPONSE)).fetch(NOW)
    self.assertEqual(snapshot.plan_name, "plus")
    self.assertEqual(snapshot.quotas[0].remaining_percent, 77)
    self.assertEqual(snapshot.quotas[1].remaining_percent, 80)
    self.assertEqual(snapshot.quotas[2].remaining, 2)


def test_codex_snapshot_serialization_preserves_plan_name():
    raw = dict(BASE_SNAPSHOT, plan_name="plus")
    snapshot = AccountSnapshot.from_dict(raw)
    self.assertEqual(snapshot.to_dict()["plan_name"], "plus")
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_codex_provider -v`

Expected: FAIL because the Codex provider does not exist.

- [ ] **Step 3: Extend the neutral snapshot with optional `plan_name`**

Add `plan_name: Optional[str] = None` to `AccountSnapshot`, parse it with `_optional_str`, and serialize it unchanged. Existing fixtures remain valid because the field is optional.

- [ ] **Step 4: Implement Codex mapping without changing legacy modules**

Map the primary and secondary windows to percentage quotas using `100 - usedPercent`, preserving reset timestamps and window durations. Add reset credits as a count quota when the app-server supplies `availableCount`. Use `source_type="local_client"`, `source_label="Codex app-server"`, account id `openai-codex`, and a five-minute freshness policy.

- [ ] **Step 5: Verify Codex and full tests**

Run: `python3 -m unittest tests.test_usage_monitor_codex_provider -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS, including the original Codex tests.

- [ ] **Step 6: Commit**

```bash
git add codex_limit_patch/usage_monitor tests/test_usage_monitor_codex_provider.py tests/test_usage_monitor_models.py
git commit -m "Map Codex limits into usage snapshots"
```

### Task 3: Milestone 2 Live Codex Demo

**Files:**
- Modify: `.gitignore`
- Create: `codex_limit_patch/usage_monitor/live_demo.py`
- Create: `demos/milestone-2/index.html`
- Create: `demos/milestone-2/README.md`
- Create: `demos/milestone-2/demo-data.example.js`
- Test: `tests/test_usage_monitor_live_demo.py`

**Interfaces:**
- Consumes: Milestone 1 synthetic accounts plus `fetch_codex_outcome`.
- Produces: `python3 -m codex_limit_patch.usage_monitor.live_demo --output demos/milestone-2/demo-data.js` and a dashboard loading that local payload.

- [ ] **Step 1: Write failing composition tests**

```python
def test_live_demo_replaces_synthetic_openai_row():
    payload = build_live_payload(FIXTURE_PATH, codex_outcome=OUTCOME, now=NOW)
    openai = [item for item in payload["accounts"] if item["provider_id"] == "openai"]
    self.assertEqual(len(openai), 1)
    self.assertEqual(openai[0]["source_label"], "Codex app-server")


def test_live_demo_keeps_other_provider_rows():
    payload = build_live_payload(FIXTURE_PATH, codex_outcome=OUTCOME, now=NOW)
    self.assertEqual(len(payload["accounts"]), 5)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_live_demo -v`

Expected: FAIL because `live_demo.py` does not exist.

- [ ] **Step 3: Implement live payload composition and CLI**

Replace only the fixture account whose `provider_id` is `openai`; keep the remaining demo accounts and mark the payload `demo: false` for Codex plus `mixed_sources: true`. Write `demo-data.js` locally and print the path. The generated file is ignored so personal quota values are never committed.

- [ ] **Step 4: Add the preserved Milestone 2 shell and documentation**

`index.html` loads `../milestone-1/styles.css`, local `demo-data.js`, and `../milestone-1/dashboard.js`. The README documents generation, direct opening, source labels, and the fact that only the Codex row is live.

- [ ] **Step 5: Run live-safe verification**

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

Run: `python3 -m codex_limit_patch.usage_monitor.live_demo --output /tmp/codex-limit-monitor-demo-data.js`

Expected: exits 0, prints the output path, and the JSON payload contains one `source_label` equal to `Codex app-server` without account identifiers or credentials.

Run: `python3 -m py_compile codex_limit_patch/usage_monitor/*.py codex_limit_patch/usage_monitor/providers/*.py`

Expected: exit 0 with no output.

Run: `git diff --check`

Expected: exit 0 with no output.

- [ ] **Step 6: Commit**

```bash
git add .gitignore codex_limit_patch/usage_monitor/live_demo.py demos/milestone-2 tests/test_usage_monitor_live_demo.py
git commit -m "Add live Codex dashboard demo"
```
