# Usage Monitor Milestone 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-neutral usage snapshot contract, deterministic local alerts, and a polished dependency-free dashboard demo for five representative AI sources without changing existing Codex behavior.

**Architecture:** New code lives under `codex_limit_patch/usage_monitor/` and has no dependency on the Codex-specific parser. Sanitized JSON fixtures are parsed into dataclasses, alert objects are derived from those dataclasses, and a static dashboard consumes the same contract through a generated JavaScript data file.

**Tech Stack:** Python 3.8+ standard library, `unittest`, HTML5, CSS, vanilla JavaScript.

## Global Constraints

- Do not modify the existing Codex CLI, parser, display, client, or Tk overlay in this milestone.
- Do not read credentials, browser cookies, or live provider configuration.
- Keep unavailable and estimated data explicit; never invent percentages or merge currencies.
- Add no third-party runtime dependency.
- Keep the dashboard usable at 360px and desktop widths.
- Store all milestone artifacts under `demos/milestone-1/`.

---

### Task 1: Provider-Neutral Snapshot Contract

**Files:**
- Create: `codex_limit_patch/usage_monitor/__init__.py`
- Create: `codex_limit_patch/usage_monitor/models.py`
- Test: `tests/test_usage_monitor_models.py`

**Interfaces:**
- Consumes: JSON-compatible dictionaries from sanitized adapters or fixtures.
- Produces: `AccountSnapshot.from_dict(data: dict[str, Any]) -> AccountSnapshot`, `AccountSnapshot.to_dict() -> dict[str, Any]`, and `load_snapshots(data: list[dict[str, Any]]) -> list[AccountSnapshot]`.

- [ ] **Step 1: Write the failing model tests**

```python
def test_snapshot_round_trip_preserves_unknown_quota():
    raw = {
        "id": "xiaomi-main",
        "provider_id": "xiaomi",
        "provider_name": "Xiaomi MiMo",
        "account_kind": "api",
        "status": "unavailable",
        "source_type": "official_api",
        "source_label": "Official API",
        "fetched_at": "2026-07-11T02:00:00Z",
        "stale_after_seconds": 900,
        "quotas": [{"id": "balance", "label": "API balance", "unit": "CNY"}],
        "models": [],
    }
    snapshot = AccountSnapshot.from_dict(raw)
    assert snapshot.quotas[0].remaining is None
    assert snapshot.to_dict()["quotas"][0]["remaining"] is None


def test_snapshot_rejects_missing_identity():
    with self.assertRaisesRegex(ValueError, "provider_id"):
        AccountSnapshot.from_dict({"id": "broken"})
```

- [ ] **Step 2: Run the model tests and verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_models -v`

Expected: FAIL because `codex_limit_patch.usage_monitor.models` does not exist.

- [ ] **Step 3: Implement focused dataclasses and validation**

Create frozen dataclasses `QuotaWindow`, `ModelUsage`, and `AccountSnapshot`. Use explicit optional numeric fields: `used`, `limit`, `remaining`, and `remaining_percent`. Validate required non-empty strings `id`, `provider_id`, `provider_name`, `account_kind`, `status`, `source_type`, `source_label`, and `fetched_at`. Preserve `None` values in serialized output so the dashboard can distinguish unknown from zero.

```python
from typing import Optional, Tuple


@dataclass(frozen=True)
class QuotaWindow:
    id: str
    label: str
    unit: str
    used: Optional[float] = None
    limit: Optional[float] = None
    remaining: Optional[float] = None
    remaining_percent: Optional[float] = None
    resets_at: Optional[str] = None
    period_label: Optional[str] = None
    accuracy: str = "exact"


@dataclass(frozen=True)
class ModelUsage:
    model_id: str
    display_name: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost: Optional[float] = None
    currency: Optional[str] = None


@dataclass(frozen=True)
class AccountSnapshot:
    id: str
    provider_id: str
    provider_name: str
    account_kind: str
    status: str
    source_type: str
    source_label: str
    fetched_at: str
    stale_after_seconds: int
    client_name: Optional[str] = None
    quotas: Tuple[QuotaWindow, ...] = ()
    models: Tuple[ModelUsage, ...] = ()
    requests_today: Optional[int] = None
    tokens_today: Optional[int] = None
    cost_today: Optional[float] = None
    currency: Optional[str] = None
    message: Optional[str] = None
```

- [ ] **Step 4: Run the model tests and the existing suite**

Run: `python3 -m unittest tests.test_usage_monitor_models -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all existing and new tests PASS.

- [ ] **Step 5: Commit the contract**

```bash
git add codex_limit_patch/usage_monitor tests/test_usage_monitor_models.py
git commit -m "Add provider-neutral usage snapshots"
```

### Task 2: Deterministic Alert Evaluation

**Files:**
- Create: `codex_limit_patch/usage_monitor/alerts.py`
- Test: `tests/test_usage_monitor_alerts.py`

**Interfaces:**
- Consumes: `AccountSnapshot` and an aware UTC `datetime`.
- Produces: `evaluate_alerts(snapshot: AccountSnapshot, *, now: datetime, low_balance: float = 10.0) -> list[UsageAlert]`.

- [ ] **Step 1: Write failing threshold and freshness tests**

```python
def test_ten_percent_remaining_is_critical():
    snapshot = make_snapshot(remaining_percent=10)
    alerts = evaluate_alerts(snapshot, now=NOW)
    self.assertEqual(alerts[0].severity, "critical")
    self.assertEqual(alerts[0].kind, "quota")


def test_old_snapshot_is_stale():
    snapshot = make_snapshot(fetched_at="2026-07-11T01:00:00Z", stale_after_seconds=300)
    alerts = evaluate_alerts(snapshot, now=NOW)
    self.assertTrue(any(alert.kind == "stale" for alert in alerts))


def test_unknown_quota_does_not_create_fake_alert():
    snapshot = make_snapshot(remaining_percent=None)
    alerts = evaluate_alerts(snapshot, now=NOW)
    self.assertFalse(any(alert.kind == "quota" for alert in alerts))
```

- [ ] **Step 2: Run the alert tests and verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_alerts -v`

Expected: FAIL because `alerts.py` does not exist.

- [ ] **Step 3: Implement alert objects and rules**

```python
@dataclass(frozen=True)
class UsageAlert:
    account_id: str
    kind: str
    severity: str
    title: str
    message: str
    quota_id: Optional[str] = None


def quota_severity(remaining_percent: Optional[float]) -> Optional[str]:
    if remaining_percent is None:
        return None
    if remaining_percent <= 10:
        return "critical"
    if remaining_percent <= 20:
        return "warning"
    return None
```

Evaluate unavailable state first, every known percentage quota second, currency balance below `low_balance` third, and freshness last. Sort critical before warning and stale/info alerts.

- [ ] **Step 4: Run alert and full tests**

Run: `python3 -m unittest tests.test_usage_monitor_alerts -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

- [ ] **Step 5: Commit alerts**

```bash
git add codex_limit_patch/usage_monitor/alerts.py tests/test_usage_monitor_alerts.py
git commit -m "Add local quota alert evaluation"
```

### Task 3: Sanitized Multi-Provider Demo Dataset

**Files:**
- Create: `demos/milestone-1/snapshots.json`
- Create: `demos/milestone-1/README.md`
- Create: `tests/test_usage_monitor_demo.py`

**Interfaces:**
- Consumes: the snapshot contract from Task 1 and alert evaluator from Task 2.
- Produces: five valid demo snapshots for Codex, Claude Code, DeepSeek, GLM, and Xiaomi MiMo.

- [ ] **Step 1: Write the failing fixture contract test**

```python
def test_demo_contains_five_representative_sources():
    raw = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    snapshots = load_snapshots(raw["accounts"])
    self.assertEqual(
        {item.provider_id for item in snapshots},
        {"openai", "anthropic", "deepseek", "zhipu", "xiaomi"},
    )
    self.assertTrue(any(evaluate_alerts(item, now=NOW) for item in snapshots))
```

- [ ] **Step 2: Run the fixture test and verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_demo -v`

Expected: FAIL because `demos/milestone-1/snapshots.json` does not exist.

- [ ] **Step 3: Add realistic sanitized fixtures**

Use these states to exercise the UI without claiming live support:

- Codex Plus: exact local app-server quota with healthy 5-hour and warning weekly window.
- Claude Code Max: demo subscription quota with a critical 5-hour window.
- DeepSeek API: exact CNY balance plus token and request totals.
- Zhipu GLM Coding Plan: estimated local token package with an explicit `accuracy: estimated` field.
- Xiaomi MiMo API: unavailable official usage source with no invented numeric fields.

The README must state that every value is synthetic, list the launch path, and identify this as Milestone 1 rather than live provider support.

- [ ] **Step 4: Run fixture and full tests**

Run: `python3 -m unittest tests.test_usage_monitor_demo -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

- [ ] **Step 5: Commit fixtures**

```bash
git add demos/milestone-1 tests/test_usage_monitor_demo.py
git commit -m "Add multi-provider usage demo data"
```

### Task 4: Polished Static Dashboard Demo

**Files:**
- Create: `demos/milestone-1/index.html`
- Create: `demos/milestone-1/styles.css`
- Create: `demos/milestone-1/dashboard.js`
- Create: `demos/milestone-1/demo-data.js`
- Create: `codex_limit_patch/usage_monitor/demo.py`
- Modify: `demos/milestone-1/README.md`
- Test: `tests/test_usage_monitor_demo.py`

**Interfaces:**
- Consumes: `snapshots.json`, `load_snapshots`, and `evaluate_alerts`.
- Produces: `python3 -m codex_limit_patch.usage_monitor.demo --output demos/milestone-1/demo-data.js` and a dashboard that opens directly from `index.html`.

- [ ] **Step 1: Add failing generator and asset tests**

```python
def test_demo_generator_writes_browser_payload(self):
    with TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "demo-data.js"
        result = generate_demo_data(DEMO_PATH, output, now=NOW)
        self.assertEqual(result, output)
        text = output.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("window.USAGE_MONITOR_DEMO = "))
        self.assertIn('"alerts"', text)


def test_dashboard_has_required_assets(self):
    html = (DEMO_DIR / "index.html").read_text(encoding="utf-8")
    self.assertIn("styles.css", html)
    self.assertIn("demo-data.js", html)
    self.assertIn("dashboard.js", html)
```

- [ ] **Step 2: Run the demo tests and verify RED**

Run: `python3 -m unittest tests.test_usage_monitor_demo -v`

Expected: FAIL because the generator and dashboard assets do not exist.

- [ ] **Step 3: Implement the deterministic browser payload generator**

`generate_demo_data` loads accounts, evaluates alerts, and writes exactly one JavaScript assignment using `json.dumps(..., ensure_ascii=False, indent=2)`. The generated payload contains `generated_at`, `accounts`, and serialized `alerts`. The module CLI accepts `--input`, `--output`, and optional `--now` for reproducible snapshots.

- [ ] **Step 4: Build the operational dashboard**

Create a full-width dark dashboard with a compact header, four summary metrics,
an alert strip, and one provider row per account. Each row must show source,
freshness, account kind, known quota bars, reset time, and unknown states. Use
semantic HTML, CSS custom properties, an 8px maximum card radius, no gradients,
and responsive grid tracks. JavaScript renders text through `textContent` and
does not inject fixture strings through `innerHTML`.

- [ ] **Step 5: Generate the committed demo payload**

Run: `python3 -m codex_limit_patch.usage_monitor.demo --input demos/milestone-1/snapshots.json --output demos/milestone-1/demo-data.js --now 2026-07-11T03:00:00Z`

Expected: prints `Wrote demos/milestone-1/demo-data.js` and exits 0.

- [ ] **Step 6: Run all automated verification**

Run: `python3 -m unittest discover -s tests`

Expected: all tests PASS.

Run: `python3 -m py_compile codex_limit_patch/usage_monitor/*.py`

Expected: exit 0 with no output.

Run: `git diff --check`

Expected: exit 0 with no output.

- [ ] **Step 7: Commit the dashboard milestone**

```bash
git add codex_limit_patch/usage_monitor demos/milestone-1 tests/test_usage_monitor_demo.py
git commit -m "Add usage monitor milestone one demo"
```
