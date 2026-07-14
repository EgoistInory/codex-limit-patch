# Expanded Provider Support Design

## Goal

Add read-only usage monitoring for Gemini CLI and three popular Chinese coding
model services without adding provider switching, proxying, account management,
or browser-cookie collection.

The existing Codex, Claude Code, and DeepSeek adapters remain behaviorally
unchanged. The installed demo and macOS menu-bar commands gain the new rows
automatically.

## Selected Providers And Sources

### Gemini CLI

Read token totals from Gemini CLI session files under the configured Gemini
home. Current Gemini CLI JSONL records attach input, output, cached, thought,
tool, and total token counts to model messages.

This adapter is a local estimate. It does not read `oauth_creds.json`, call
Google's private Code Assist quota API, or claim to know subscription quota.
That avoids reusing OAuth credentials outside the official client and remains
useful for API-key, Vertex AI, and OAuth users alike.

### Kimi Code

Use an explicitly configured `KIMI_CODE_API_KEY` or `KIMI_API_KEY` with
`GET https://api.kimi.com/coding/v1/usages`. Map the overall allowance and
returned rolling limits into request-count quota windows with exact reset
timestamps.

### Zhipu GLM Coding Plan

Use `ZHIPU_API_KEY` or `Z_AI_API_KEY` with the read-only personal quota endpoint
`GET https://open.bigmodel.cn/api/monitor/usage/quota/limit`. Map each returned
token or time limit independently; do not invent missing windows or team scope.

### MiniMax Token Plan

Use `MINIMAX_CODING_API_KEY` or `MINIMAX_API_KEY` with the official Token Plan
endpoint `GET https://www.minimax.io/v1/token_plan/remains`. Prefer the general
model lane and expose its rolling and weekly remaining percentages and reset
times. Other service lanes stay available for future model-level expansion.

## Architecture

Each provider owns a descriptor, credential resolver, bounded read-only client,
response parser, and fetch strategy. Network adapters enforce an exact HTTPS
host and path, a ten-second timeout, a one MiB response cap, sanitized errors,
and no credential serialization.

A new supported-provider collection entrypoint returns providers in this order:

1. OpenAI / Codex
2. Anthropic / Claude Code
3. Google / Gemini CLI
4. DeepSeek
5. Kimi Code
6. Zhipu GLM
7. MiniMax

The historical three-provider collector remains as a compatibility wrapper.
The demo command and menu-bar process use the expanded entrypoint.

## Failure Behavior

- A missing local Gemini session directory is `Not configured`.
- A missing API key is `Not configured` and does not create a global alert.
- Invalid credentials, network errors, and malformed successful responses are
  real provider failures and remain visible as alerts.
- Missing metrics remain absent; a provider row never derives a percentage from
  an unrelated balance, token count, or plan name.

## Testing

- Gemini tests cover JSONL parsing, date filtering, per-model totals, malformed
  records, and missing directories.
- Each HTTP adapter test covers parsing, exact endpoint enforcement, auth
  headers, timeout and response limits, missing keys, and secret exclusion.
- Collector and menu tests cover stable provider order and unconfigured rows.
- Final verification runs the complete unit suite, compile and diff checks, a
  live collection without exposing secrets, and the installed menu-bar process.

## Non-Goals

- Browser-cookie or web-session import.
- Gemini OAuth credential reuse or private quota API access.
- Team or organization quota configuration.
- Provider/model switching, request routing, or API proxying.
- Xiaomi MiMo and Alibaba Bailian until a suitable explicit-key read-only path
  is both stable and useful.
