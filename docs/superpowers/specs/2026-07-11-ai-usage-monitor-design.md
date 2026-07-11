# AI Usage Monitor Design

## Goal

Evolve this repository into a local-first usage and quota monitor for AI coding
clients and model providers. The product displays usage, quota windows, reset
times, cost, data freshness, and alerts. It does not configure providers, write
client settings, switch accounts, or route model traffic.

The existing Codex CLI and Tk overlay remain supported and unchanged. New work
is additive and consumes their output through an adapter.

## Product Model

The product keeps three concepts separate:

1. Client: Codex, Claude Code, Gemini CLI, OpenCode, and similar local tools.
2. Provider account: OpenAI, Anthropic, DeepSeek, Zhipu, Xiaomi, or an aggregator.
3. Model: GPT, Claude, DeepSeek, GLM, MiMo, and individual model versions.

An account can expose subscription quota windows, API balance, token usage,
cost, or only a subset. Missing values stay unknown. The UI never derives a
fake percentage from incompatible metrics.

## Considered Approaches

### Rewrite the repository as a desktop application

This gives a clean architecture but risks breaking the working Codex utility
and delays the first usable result.

### Extend the existing Codex dataclasses for every provider

This is initially fast but couples Codex-specific concepts such as the five-hour
window and reset bank to unrelated providers.

### Add a provider-neutral core beside the existing implementation

This is the selected approach. A new normalized snapshot protocol, adapters,
alert evaluator, and dashboard are added without changing the Codex contract.
The Codex adapter maps the existing state into the neutral protocol.

## Architecture

```text
Provider adapters
  Codex app-server | Claude local data | provider billing APIs | demo fixtures
         |
         v
Normalized usage snapshots
  account + client + models + quota windows + cost + provenance
         |
         v
Aggregation and alert evaluation
         |
         +--> JSON snapshot / CLI
         +--> dashboard demo
         +--> future desktop tray and always-on-top widget
```

Each adapter is read-only and returns a complete snapshot or a typed unavailable
result. Adapters do not know about UI layout. The UI does not parse provider
responses.

Each provider will eventually own a descriptor and an ordered set of fetch
strategies. A descriptor defines stable identity, labels, capabilities, and
freshness policy. Strategies represent concrete sources such as a local CLI,
OAuth usage endpoint, API key balance endpoint, browser session, or local log
estimate. A refresh records attempted strategies and sanitized failures, then
uses the best successful result or the last trustworthy cached snapshot.

## Normalized Contract

An account snapshot contains:

- Stable account and provider identifiers with display labels.
- Optional client association.
- Account kind: subscription, API billing, local estimate, or mixed.
- Quota windows with used/remaining values, units, period labels, and reset time.
- Token and cost totals for a named period.
- Optional per-model metrics.
- Source metadata: official API, local client, imported fixture, or estimate.
- Freshness and availability state with a sanitized error message.

Every metric records whether it is exact, estimated, or unavailable. Secrets,
raw authentication responses, and full account identifiers are excluded.
Account identity and plan metadata remain isolated inside their provider and
are never used as fallback labels for another provider.

## Alerts

The first alert engine is deterministic and local:

- Warning when remaining quota is at or below 20 percent.
- Critical when remaining quota is at or below 10 percent.
- Warning when an API balance is below a configurable amount.
- Stale when the source has not refreshed within its adapter's freshness window.
- Unavailable when an adapter fails and has no previous good snapshot.
- Future pace alerts may predict whether a quota will last until reset, but only
  when a window exposes enough elapsed-time and reset data.

Alerts are data objects, not UI strings, so future desktop notifications can use
the same rules.

## Interface Direction

The main dashboard is a compact operational surface, not a marketing page.
The top band shows total active accounts, current alerts, today's cost, and
freshness. Provider rows show recognizable names, quota bars, reset times, and
source labels. A small always-on-top widget shows only urgent quota values and
can be dismissed by closing its process.

The first visual milestone is a dependency-free HTML dashboard backed by demo
snapshots for Codex, Claude Code, DeepSeek, GLM, and MiMo. It establishes the
information hierarchy before selecting a desktop shell. A later milestone can
wrap the same UI in Electron or Tauri after packaging requirements are measured.

## Security

- Prefer local authenticated client protocols and official read-only APIs.
- API credentials are opt-in and must eventually use the operating system keychain.
- Never store credentials in fixtures, logs, SQLite, or exported snapshots.
- Never read unrelated browser cookies or client credentials implicitly.
- Show the source and collection method for every account.
- Bound every subprocess, network request, and interactive probe with a timeout.

## CodexBar Reference Decisions

CodexBar is the primary reference for provider boundaries and compact menu-bar
presentation: <https://github.com/steipete/CodexBar>. Its descriptor-driven
provider pipeline, last-known-good degradation, merged status item, reset
countdowns, and explicit source labels fit this product. This project does not
copy CodexBar's provider settings surface or broad credential import behavior.

Provider semantics remain source-specific:

- DeepSeek exposes an API balance, not a session or weekly percentage.
- Zhipu/z.ai can expose token, time, and MCP windows depending on account type.
- Xiaomi MiMo can expose balance and token-plan data through an authenticated
  console session; local wrapper logs are usage estimates, not platform quota.
- Codex and Claude subscription windows remain separate from OpenAI and
  Anthropic organization API billing.

## Demo Milestones

1. Neutral snapshot contract, alert rules, fixture validation, and static dashboard.
2. Existing Codex adapter feeding the dashboard without changing the old CLI.
3. Claude Code local usage adapter and combined live dashboard.
4. Opt-in official API adapters for providers with stable usage or balance APIs.
5. Desktop tray, persistent widget, notifications, and packaged releases.

Each milestone has its own fixture or launch command and a short verification
record under `demos/`.

## Testing

- Unit tests validate contract serialization, percentages, alert thresholds,
  stale behavior, and unavailable sources.
- Adapter tests use saved sanitized provider responses.
- Existing Codex tests remain unchanged and must continue to pass.
- Dashboard demos are checked at desktop and narrow widths before packaging.

## Explicit Non-Goals

- Provider configuration or one-click switching.
- API proxying, request routing, or failover.
- Editing Claude Code, Codex, or other client configuration files.
- Guessing subscription limits or merging incompatible billing periods.
