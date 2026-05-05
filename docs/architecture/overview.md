# Architecture Overview

## Purpose

DevSynapse AI is a TUI-first local coding agent. Its main concerns are:

- LLM orchestration and model routing;
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

Main files:

- [devsynapse/cli.py](../../devsynapse/cli.py)
- [devsynapse/tui.py](../../devsynapse/tui.py)
- [devsynapse.sh](../../devsynapse.sh)

`devsynapse.cli:main` is the package script entry point and launches the TUI.
Operator actions are exposed as slash commands inside the TUI, not as external
subcommands.

## Canonical Operator Flow

The canonical user-facing command is:

```bash
devsynapse
```

The command opens the Textual TUI. Provider setup, status, usage, budget,
routing, project selection and shell-tool execution are handled by slash
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
- `deepseek.py`: provider transport, payload construction, pricing and
  `LLMResult` response contract.
- `routing.py`: model selection, budget-aware routing and learned route
  preferences.
- `prompts.py`: system prompt template construction.
- `opencode_bridge.py`: command parsing, validation, authorization, path
  scoping and execution for `bash`, `read`, `glob`, `grep`, `edit` and `write`.
- `core/memory/`: SQLite-backed stores for conversations, projects, settings,
  learning, procedural memories, skills and agent runs.
- `plugin_system.py`: lifecycle and command extension points.
- `correlation.py`: conversation and tool-run ID generation.

## Runtime Configuration

Runtime paths are resolved in [config/settings.py](../../config/settings.py).
Defaults follow XDG-style user directories:

- config: `~/.config/devsynapse-ai/.env`
- data: `~/.local/share/devsynapse-ai/data`
- logs: `~/.local/state/devsynapse-ai/logs`

`DEVSYNAPSE_HOME` relocates all three under one directory. Individual
`DEVSYNAPSE_CONFIG_FILE`, `DEVSYNAPSE_DATA_DIR` and `DEVSYNAPSE_LOGS_DIR`
overrides are also supported.

Settings import is intentionally tolerant of read-only config files so basic TUI
commands such as `--help` do not fail before argument parsing. Agent runs that
use memory still require a writable data directory.

## Runtime Principles

- Keep transport, orchestration, persistence and command execution separate.
- Treat SQLite migrations as the data contract for local state.
- Keep mutating command execution project-aware and auditable.
- Persist command failures and policy blocks so later turns can continue with
  the original task context.
- Prefer explicit provider configuration and local runtime files over hardcoded
  credentials or repository-local secrets.
