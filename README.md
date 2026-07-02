# Codex Limit Patch

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

If installed via `pip`, you can run it from anywhere. Alternatively, from this project directory without installation:

```bash
python -m codex_limit_patch --mode pill
python -m codex_limit_patch --mode expanded
python -m codex_limit_patch --mode json
```

If `codex` is not on `PATH`, set `CODEX_BIN` or pass `--codex-bin`:

```bash
CODEX_BIN=/path/to/codex python -m codex_limit_patch --mode expanded
python -m codex_limit_patch --codex-bin "C:\Path\To\codex.exe" --mode expanded
```

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
python -m codex_limit_patch --settings settings.example.json
```

## Debug Logging

Use `--debug-log` to record reset bank response shape diagnostics:

```bash
python -m codex_limit_patch --debug-log ./logs/reset-bank.log
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
