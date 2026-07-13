# macOS Menu Bar Monitor Design

## Goal

Provide an always-available macOS menu-bar view for Codex, Claude Code, and
DeepSeek usage without requiring the user to open a browser or regenerate a
snapshot manually.

## Product Shape

The existing HTML dashboard remains the detailed view. A new optional macOS
menu-bar process becomes the daily surface:

- compact status title showing health and alert count;
- one read-only summary row per live provider;
- source and last-refresh information;
- Refresh Now, Open Dashboard, and Quit commands;
- automatic refresh every 60 seconds, clamped to at least 15 seconds.

The monitor does not configure providers, switch models, proxy requests, or
persist credentials.

## Architecture

`usage_monitor.collector` owns one complete three-provider collection pass and
returns the existing normalized dashboard payload. Both the CLI snapshot
generator and menu-bar process use this function.

`usage_monitor.menubar_model` converts a normalized payload into small,
deterministic menu rows and a compact title. It has no GUI dependency and is
fully unit tested.

`usage_monitor.macos_menubar` is a thin optional `rumps` adapter. Provider reads
run on a daemon worker thread. A short main-loop timer applies completed results
to AppKit UI objects, while a second timer schedules periodic refreshes. Each
successful collection also rewrites the ignored Milestone 4 `demo-data.js` so
Open Dashboard always starts with the current snapshot.

## Safety And Failure Behavior

- The process is supported only on macOS and binds no network port.
- `rumps` is an optional dependency; all existing commands remain dependency-free.
- DeepSeek keys are resolved only through the existing environment-variable
  path and never appear in menu text or generated snapshots.
- A failed provider remains an explicit unavailable row through the existing
  provider outcome contract.
- An unexpected collection failure keeps the last successful values visible,
  changes the title to an error state, and exposes a sanitized one-line message.
- Concurrent refreshes are suppressed.

## Dashboard Behavior

Open Dashboard launches the existing local Milestone 4 live HTML file. The
menu-bar process refreshes its data file in the background. The live page uses
a 60-second document reload so an already-open dashboard follows those writes.

## Packaging

Install with `pip install -e '.[macos-menubar]'`, then run
`ai_usage_monitor_menubar`. The optional extra pins `rumps` to the compatible
0.x release line. Windows installation and existing commands do not pull this
dependency.

## Verification

- Unit tests cover collection injection, title/row formatting, unavailable
  sources, alert counts, and sanitized errors.
- Existing full suite, Python compile, and JavaScript syntax checks remain green.
- Runtime verification installs the optional extra, starts the process, confirms
  the process remains alive, and checks that a fresh ignored dashboard payload
  is written without sensitive fields.
