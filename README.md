# Codex Limit Patch

[English](README.md) | [中文](README_zh.md)

Cross-platform local viewer for Codex usage limits and Reset Bank state.

By default, it reads the local Codex app-server protocol:

- `account/rateLimits/read`
- `rateLimitResetCredits`

This is a lightweight account-state query. It does not start a Codex thread or model turn, and it does not request model generation, so it should not consume ChatGPT/Codex package tokens. It only reads quota/reset-bank state exposed by the local authenticated Codex app-server. As with any account endpoint, OpenAI's service-side behavior is authoritative if it changes later.

The tool is intentionally conservative. If the current Codex app-server only returns a total reset count, it shows the total count and says details are unavailable. It does not invent reset credit source, acquired time, expiry time, or usage history.

Default mode does not read `~/.codex/auth.json`.

## Supported Platforms

- Windows
- macOS

Python 3.8+ is required. No third-party Python packages are required.

## Installation

You can install it locally using `pip`:

```bash
pip install -e .
```

## Usage

If installed via `pip`, you can use the CLI command directly from anywhere:

```bash
codex_limit_patch --mode pill
codex_limit_patch --mode expanded
codex_limit_patch --mode json
```

Alternatively, from this project directory without installation (running the module):

```bash
python -m codex_limit_patch --mode pill
```

If `codex` is not on `PATH`, set `CODEX_BIN` or pass `--codex-bin`:

```bash
CODEX_BIN=/path/to/codex codex_limit_patch --mode expanded
codex_limit_patch --codex-bin "C:\Path\To\codex.exe" --mode expanded
```

To keep the limit state visible as a small always-on-top patch, run the overlay:

```bash
codex_limit_patch_overlay --mode pill
codex_limit_patch_overlay --mode expanded --refresh-sec 60
```

The overlay reuses the same local Codex app-server data reader, parser, and text rendering logic. On macOS, it tries to attach near the top-right of the Codex window. If Accessibility permission is not available, or if the Codex window cannot be found, it falls back to the screen top-right. You can also pin it manually:

```bash
codex_limit_patch_overlay --geometry "+1200+20" --no-track-codex
```

Drag the overlay to move it, double-click to refresh immediately, and press `Esc` or `Ctrl-Q` to close it.

## Multi-provider Usage Monitor

The original Codex CLI and always-on-top overlay remain unchanged. A separate
dashboard now normalizes read-only usage information from multiple clients and
providers without adding provider configuration or model switching.

| Provider / client | Current data | Source |
| --- | --- | --- |
| Codex | Subscription windows and Reset Bank | Local Codex app-server |
| Claude Code | Requests and token totals | Allowlisted local JSONL fields |
| Gemini CLI | Today's requests and token totals by model | Allowlisted local JSONL fields |
| DeepSeek | CNY/USD balance, granted and paid components | Official balance API |
| Kimi Code | Rolling and weekly request limits | Official usage API |
| Zhipu GLM Coding Plan | Token and MCP/time quotas | Official quota API |
| MiniMax Coding Plan | Rolling and weekly token limits | Official Token Plan API |
| Xiaomi MiMo | Reserved Demo row | Adapter planned for later |

Generate a local dashboard payload:

```bash
python3 -m codex_limit_patch.usage_monitor.three_source_demo
# or, after installation
ai_usage_monitor_demo
```

Gemini reads only allowlisted usage fields from local Gemini CLI sessions under
`~/.gemini/tmp`; it does not reuse Gemini OAuth credentials or claim to expose
subscription limits. API-backed providers are optional and use these variables:

| Provider | Environment variables, in precedence order |
| --- | --- |
| DeepSeek | `DEEPSEEK_API_KEY`, `DEEPSEEK_KEY` |
| Kimi Code | `KIMI_CODE_API_KEY`, `KIMI_API_KEY` |
| Zhipu GLM | `ZHIPU_API_KEY`, `Z_AI_API_KEY` |
| MiniMax | `MINIMAX_CODING_API_KEY`, `MINIMAX_API_KEY` |

Without a key, the provider remains visibly **Not configured** rather than
showing synthetic data as live. Keys stay in process memory and are never
written to the generated JavaScript payload. Alternate environment variable
names can be selected with `--deepseek-api-key-env`, `--kimi-api-key-env`,
`--zhipu-api-key-env`, and `--minimax-api-key-env`.

Open `demos/milestone-4/index-live.html` after generation. The committed
`demos/milestone-4/index.html` is a credential-free example. Earlier milestone
demos remain available as implementation snapshots.

### macOS Menu Bar

For an always-available view without keeping a browser open, install the
optional macOS companion:

```bash
pip install -e '.[macos-menubar]'
ai_usage_monitor_menubar
```

The menu bar refreshes in the background every 60 seconds. It shows one compact
row per live provider, per-window reset countdowns, alert state, data refresh
time, and exact source labels. An optional provider without credentials is
shown as **Not configured** and does not raise a global alert. Use **Refresh
Now** for an immediate read or **Open Dashboard** for the full page. The process
stores no credentials and does not expose a local network service.

The pill mode is compact:

```text
Codex 5h 78% | Week 64% | Reset x2
```

If reset bank is unavailable:

```text
Codex 5h 78% | Week 64% | Reset ?
```

Expanded mode includes the Reset Bank section:

```text
Codex 5h remaining: 78%
Codex 5h resets at: 2026-07-02 20:59
Weekly remaining: 64%
Weekly resets at: 2026-07-09 09:35

Reset Bank
Available: 2
Snapshot: 2026-07-02 14:25
Details: not provided by supported Codex app-server
Reset credit details not available from local safe sources.
```

When future Codex versions return per-credit details, the compatible parser displays:

```text
#1 Available | Referral
Granted: 2026-07-01 10:22
Expires: 2026-07-31 23:59
expires in 29d
```

## Data Source Levels

### Level 1: stable app-server

Default source. The tool calls only:

```text
account/rateLimits/read
```

It displays:

- 5h limit remaining
- weekly limit remaining
- 5h / weekly `resetsAt`
- `rateLimitResetCredits.availableCount`

If the app-server only returns `availableCount`, the UI only shows `Reset xN` and does not invent per-credit details.

If the live `account/rateLimits/read` call fails, the tool read-only scans the newest rollout `rate_limits` snapshot under `~/.codex/sessions/` and `~/.codex/archived_sessions/`. Fallback output is marked `cached` and includes its source, snapshot time, and live error. It does not read `auth.json`. Local snapshots may be stale and are only a temporary reference.

### Level 2: local safe probe

If app-server does not provide per-credit details, the tool performs a local read-only probe without reading `auth.json` or tokens.

Allowed directories:

- `~/.codex/sessions/`
- `~/.codex/archived_sessions/`
- `~/.codex/logs/` if present

It searches only candidate lines containing these keywords:

- `granted_at`
- `grantedAt`
- `expires_at`
- `expiresAt`
- `rateLimitResetCredits`
- `rate-limit-reset-credits`
- `resetBank`
- `availableCount`
- `credits`

If it clearly finds a JSON line containing per-credit `granted_at` / `expires_at` or compatible camelCase fields, it parses and displays those details. If it only finds `availableCount`, it still only shows `Reset xN`.

If no detail rows are found:

```text
Reset credit details not available from local safe sources.
```

### Level 3: experimental private endpoint

Disabled by default.

Only when both settings are explicitly true will the tool read local Codex auth and call the private backend endpoint:

```json
{
  "resetBank": {
    "enablePrivateEndpoint": true,
    "privateEndpointWarningAccepted": true
  }
}
```

Endpoint:

```text
GET https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
```

This mode is experimental and unsupported:

- the endpoint is not the stable Codex app-server interface
- it may change or disappear at any time
- it needs local Codex/ChatGPT auth
- it reads `~/.codex/auth.json` only after explicit opt-in
- tokens are used only in local memory
- tokens, account ids, full responses, cookies, and auth headers are not written to logs
- no data is uploaded to third parties

Recommended path: wait for official app-server support for detailed reset credit rows before treating per-credit details as a formal capability.

## Reset Bank Behavior

Reset Bank shows current available Codex earned reset credits.

- If Codex app-server only returns a total, the tool only shows the total.
- Acquired time and expiry time are shown only when the API returns matching fields.
- The tool does not guess reset credit source, acquired time, or expiry time.
- The tool does not assume a 30-day expiry unless the API returns an expiry field.
- The tool does not automatically consume reset credits.
- If future Codex app-server responses include richer detail rows, the parser is designed to display them without changing the UI contract.

## Parsed Fields

For reset totals, the parser accepts compatible fields such as:

- `availableCount`
- `count`
- `balance`

For detail arrays, it looks for:

- `credits`
- `items`
- `entries`
- `resetBank`

Acquired time priority:

1. `acquiredAt`
2. `earnedAt`
3. `grantedAt`
4. `createdAt`
5. `issuedAt`
6. `awardedAt`
7. `receivedAt`

Expiry time priority:

1. `expiresAt`
2. `expirationAt`
3. `expireAt`
4. `validUntil`
5. `endsAt`
6. `deadlineAt`

Supported timestamp forms:

- Unix seconds
- Unix milliseconds
- ISO strings
- RFC3339-like strings
- date-like strings when Python can parse them safely

## Settings

See `settings.example.json`:

```json
{
  "resetBank": {
    "showInPill": true,
    "showDetailsInExpanded": true,
    "warnExpireWithinHours": 72,
    "dangerExpireWithinHours": 24,
    "showUnknownDetails": true,
    "enablePrivateEndpoint": false,
    "privateEndpointWarningAccepted": false
  }
}
```

Pass a settings file with:

```bash
codex_limit_patch --settings settings.example.json
```

## Debug Logging

Use `--debug-log` to record reset bank response shape diagnostics:

```bash
codex_limit_patch --debug-log ./logs/reset-bank.log
```

The debug log records structural shape, whether reset bank exists, whether only `availableCount` is present, and whether detail counts differ from the backend snapshot.

It does not log tokens, auth headers, API keys, account ids, cookies, or raw response JSON.

## Tests

Run:

```bash
python -m unittest discover -s tests
```

The parser tests cover:

- only `availableCount`
- `availableCount` equal to `0`
- missing reset bank data
- `credits` / `items` detail arrays
- Unix seconds, Unix milliseconds, and ISO timestamps
- acquired time field priority
- status mappings such as `redeemed` / `consumed` to `used`
- expiry-based `expired` detection
- backend count versus detail count mismatch warnings
- fully unknown fields without crashing
- local safe probe detail discovery
- local safe probe ignoring count-only records
- remaining-percent display

## Limits

This project uses local Codex app-server data by default. It is not an official billing ledger. It cannot prove the source of a reset credit unless the API response explicitly provides source-like fields.

Per-reset `granted` / `expires` values are not currently guaranteed by the stable app-server surface. The tool will show them only when a safe local source or explicitly enabled experimental private endpoint returns those fields.
