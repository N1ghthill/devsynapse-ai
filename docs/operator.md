# Transitional v1 Operator Guide

## Status

This guide describes the current Python/Textual v1 implementation for
contributors and migration testing.

It is not the target end-user experience. The target is a packaged desktop
application with guided GitHub connection and no terminal requirement. See the
[product contract](product-contract.md) and [roadmap](roadmap.md).

## Current Development Setup

From a source checkout:

```bash
python3 -m venv venv
source venv/bin/activate
make install-dev
make run
```

The current runtime uses:

```text
~/.config/devsynapse-ai/.env
~/.config/devsynapse-ai/ui.json
~/.local/share/devsynapse-ai/data/devsynapse_memory.db
~/.local/state/devsynapse-ai/logs/devsynapse.log
```

`DEVSYNAPSE_HOME=/temporary/path` isolates config, data and logs for testing.

## Current TUI Capabilities

The transitional TUI currently supports:

- provider setup and selection;
- project registration and selection;
- conversation history and memory;
- Build and Plan modes;
- usage and budget telemetry;
- appearance preferences;
- a generic local command bridge.

Use `/help` inside the current TUI for its command list. Those commands are not
the target desktop interaction model and should not receive new product
features.

## Current Safety Limitation

Build mode uses the legacy trusted command bridge and executes with the current
OS user's permissions. It is not a sandbox.

For current-core testing:

- use Plan mode for inspection;
- use disposable projects and `DEVSYNAPSE_HOME` paths;
- keep provider keys outside the repository;
- do not configure GitHub production credentials in the transitional UI;
- treat generic command execution as development-only.

## Verification

```bash
make verify
make migration-status
```

The TUI smoke test remains part of current verification only while the TUI is
in the repository.

## Target Replacement

The desktop migration replaces:

| Current v1 | Target |
|---|---|
| shell install and wrappers | signed/packaged desktop artifacts |
| TUI and slash commands | React conversation and visual flows |
| `.env` setup | guided settings and secure credential storage |
| generic command bridge | typed Git and GitHub operations |
| provider/usage sidebars | internal diagnostics or advanced settings |
| terminal project paths | native folder selection and GitHub repository connection |

The TUI can be retired from releases after desktop packaging, visual setup,
typed operations and data migration are complete.
