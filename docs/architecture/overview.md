# Architecture Overview

## Purpose

DevSynapse AI is a TUI-first local coding agent. Its main concerns are:

- LLM orchestration and manual model selection;
- persistent local memory and project registry state;
- constrained command execution against local projects;
- plugin hooks around lifecycle and command events.

The supported operator surface is the Textual TUI.

## High-Level Flow

```text
Textual TUI
        |
        v
DevSynapseBrain
  - prompt construction
  - route selection
  - tool-call loop
  - usage telemetry
        |
        +--> DeepSeekClient / compatible providers
        |
        +--> OpenCodeBridge constrained local tools
        |
        v
SQLite memory stores + runtime config
```

## Entry Points

Operator entry points:

- `~/.local/bin/devsynapse`
- `~/.local/bin/update-devsynapse`
- `~/.local/bin/uninstall-devsynapse`

Main source files:

- [devsynapse/cli.py](../../devsynapse/cli.py)
- [devsynapse/tui.py](../../devsynapse/tui.py)
- [devsynapse.sh](../../devsynapse.sh)

`devsynapse.cli:main` is the package script entry point and launches the TUI.
`devsynapse.sh` is an internal checkout launcher used by the installed wrapper.
Operator actions are exposed as slash commands inside the TUI, not as external
subcommands.

## Canonical Operator Flow

The canonical user-facing command is:

```bash
devsynapse
```

The command opens the Textual TUI. Provider setup, status, usage, budget,
model selection, project selection and shell-tool execution are handled by slash
commands inside the TUI. External operator subcommands are rejected by design to
avoid competing flows.

## Core Services

Main files:

- [core/brain.py](../../core/brain.py)
- [core/deepseek.py](../../core/deepseek.py)
- [core/routing.py](../../core/routing.py)
- [core/prompts.py](../../core/prompts.py)
- [core/opencode_bridge.py](../../core/opencode_bridge.py)
- [core/plugin_system.py](../../core/plugin_system.py)
- [core/correlation.py](../../core/correlation.py)
- [core/memory/system.py](../../core/memory/system.py)

Responsibilities:

- `brain.py`: agent-run context, tool-call orchestration, auto-execution loop,
  output sanitization and telemetry recording.
- `command_extraction.py`: conversion of structured tool calls and fallback
  text command extraction into OpenCode command strings.
- `autoexec_policy.py`: auto-execution round limits, low-risk command checks
  and retry/replay decisions.
- `checklist.py`: objective checklist helpers for implementation tasks.
- `deepseek.py`: provider transport, streaming/non-streaming payload
  construction, pricing and `LLMResult` response contract.
- `routing.py`: manual provider/model selection with configured-provider
  fallback when the selected provider has no API key.
- `prompts.py`: system prompt template construction.
- `opencode_bridge.py`: command parsing, validation, authorization, path
  scoping and execution for `bash`, `read`, `glob`, `grep`, `edit` and `write`.
- `core/memory/`: SQLite-backed stores for conversations, projects, settings,
  learning, procedural memories, skills and agent runs.
- `core/memory/protocol.py`: brain-facing memory protocol plus optional
  capability adapter.
- `plugin_system.py`: lifecycle and command extension points.
  `DevSynapseBrain` accepts an injected plugin manager for isolated tests and
  runtime composition; the module-level singleton remains the default.
- `correlation.py`: conversation and tool-run ID generation.
- `db.py`: SQLite migration utilities and the shared connection helper used by
  memory stores.
- `async_utils.py`: shared offload helper for blocking provider and SQLite work;
  it avoids `asyncio.to_thread` so shutdown and SQLite callbacks stay testable
  on the supported Python runtime.

## Runtime Configuration

Runtime paths are resolved in [config/settings.py](../../config/settings.py).
Defaults follow XDG-style user directories:

- config: `~/.config/devsynapse-ai/.env`
- TUI preferences: `~/.config/devsynapse-ai/ui.json`
- data: `~/.local/share/devsynapse-ai/data`
- logs: `~/.local/state/devsynapse-ai/logs`

`DEVSYNAPSE_HOME` relocates all three under one directory. Individual
`DEVSYNAPSE_CONFIG_FILE`, `DEVSYNAPSE_DATA_DIR` and `DEVSYNAPSE_LOGS_DIR`
overrides are also supported.

TUI styles are loaded from `.tcss` files under `devsynapse/styles/`. The runtime
`ui.json` selects a supported theme (`dark`, `light`, `dracula`) and layout
(`default`, `dense`) without changing Python code.

Settings import is intentionally tolerant of read-only config files so basic TUI
commands such as `--help` do not fail before argument parsing. Agent runs that
use memory still require a writable data directory.

## Runtime Principles

- Keep transport, orchestration, persistence and command execution separate.
- Treat SQLite migrations as the data contract for local state.
- Keep mutating command execution project-aware and auditable.
- Persist command failures and policy blocks so later turns can continue with
  the original task context.
- Prefer explicit provider configuration through the TUI setup form and local
  runtime files over hardcoded credentials or repository-local secrets.
- Keep model selection manual and provider-aware: use the provider/model chosen
  in the TUI and only fall back when that provider is not configured.
