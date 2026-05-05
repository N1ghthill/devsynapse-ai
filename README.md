# DevSynapse AI

DevSynapse AI is a local-first terminal UI coding agent for DeepSeek-compatible
LLM providers. It runs as a Textual TUI, keeps project memory in SQLite, routes
between configured models, and executes constrained local commands through a
project-aware bridge. The product has one operator entry point: `devsynapse`.

## Product Surface

- opens a single terminal UI for chat, setup, status and command execution;
- calls DeepSeek, OpenRouter, OpenCode Zen or OpenCode Go when a matching API key
  is configured;
- persists conversations, project registry data, task runs, model routing
  telemetry, procedural memories and skills in SQLite;
- executes local tool calls through `bash`, `read`, `glob`, `grep`, `edit` and
  `write` with command validation and project scoping;
- tracks token usage and estimated LLM cost from provider responses;
- keeps setup and operations in slash commands inside the TUI.

## Requirements

- Python 3.10 or newer; CI/development currently uses Python 3.13.
- Linux or another Unix-like shell environment for the installer scripts.
- At least one provider API key:
  `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OPENCODE_ZEN_API_KEY` or
  `OPENCODE_GO_API_KEY`.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
make install-dev
```

Configure a provider key in the runtime config:

```bash
mkdir -p ~/.config/devsynapse-ai
cp .env.example ~/.config/devsynapse-ai/.env
$EDITOR ~/.config/devsynapse-ai/.env
```

Start DevSynapse:

```bash
./devsynapse.sh
```

The installer creates the same alias:

```bash
devsynapse
```

## Canonical Flow

`devsynapse` opens the terminal UI. That is the only supported operator flow.
Provider setup, status, usage, budget, routing, project selection and shell-tool
commands are slash commands inside the TUI. External subcommands such as
`devsynapse providers`, `devsynapse connect ...` or `devsynapse tui` are
intentionally rejected so the product has one clear entry point.

Inside the TUI, DevSynapse exposes operational slash commands:

```text
/connect <provider> <api-key>    save DeepSeek/OpenRouter/OpenCode keys
/providers                       show configured provider status
/discover                        refresh the model catalog
/models [provider]               list known models and pricing
/budget                          show daily/monthly plan usage
/budget daily|monthly <usd>      set budget limits
/router                          show intelligent routing policy
/router on|off                   enable or disable model routing
/router economy on|off           toggle automatic economy mode
/router adaptive on|off          toggle cheapest-model override
/usage                           show recent model/cost telemetry
!<command>                       run a shell command as a tool result
```

The TUI keeps the conversation log, input line, session state, provider status,
budget state and common commands visible in one terminal screen. It supports the
slash commands above plus shortcuts such as `Ctrl+H` for help, `Ctrl+N` for a
new conversation and `Ctrl+R` to refresh status.

## Runtime State

By default DevSynapse stores user runtime files outside the source checkout:

- config: `~/.config/devsynapse-ai/.env`
- SQLite data: `~/.local/share/devsynapse-ai/data/devsynapse_memory.db`
- logs: `~/.local/state/devsynapse-ai/logs/devsynapse.log`

Set `DEVSYNAPSE_HOME=/path/to/runtime` to keep config, data and logs together
under one directory. The more specific `DEVSYNAPSE_CONFIG_FILE`,
`DEVSYNAPSE_DATA_DIR` and `DEVSYNAPSE_LOGS_DIR` variables can override each path.
Set `ASSISTANT_USER_NAME` in the runtime config or environment to personalize
the system prompt; the default prompt is generic for distributed installs.
Set `LLM_STREAMING_ENABLED=false` to force non-streaming provider responses.

The settings loader creates these files on a best-effort basis. Read-only
runtime config should not break commands such as `devsynapse --help`; commands
that need persistent memory still require a writable SQLite data directory.

## Common Commands

```bash
make install-dev        # install runtime and test dependencies
make run                # start the TUI
make tui-smoke          # check TUI launcher help
make lint               # run Ruff
make test               # run pytest
make script-check       # check shell and operational scripts
make verify             # lint, tests, script checks and TUI smoke checks
make migrate            # apply SQLite migrations
make migration-status   # inspect migration state
```

The Python package entry point is also declared as:

```bash
devsynapse = "devsynapse.cli:main"
```

For day-to-day operation, see [docs/operator.md](docs/operator.md).

## Project Structure

```text
devsynapse/        TUI launcher and Textual application
config/            runtime settings and command policy constants
core/              LLM orchestration, routing, memory, plugins and tools
core/memory/       SQLite-backed stores
plugins/           local plugin examples
scripts/           install, update, migration and evaluation utilities
tests/             unit and integration tests
docs/              contributor and architecture documentation
```

## Verification

Current local baseline after the TUI product cleanup:

```text
make lint        passed
make test        167 passed
make script-check passed
make tui-smoke   passed
```
