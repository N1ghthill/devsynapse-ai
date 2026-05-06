# DevSynapse AI

DevSynapse AI is a local-first terminal UI coding agent for DeepSeek-compatible
LLM providers. It runs as a Textual TUI, keeps project memory in SQLite, uses
the manually selected model, and executes constrained local commands through a
project-aware bridge.

The product is intentionally narrow: one installed app command, one TUI, one
runtime store, one install/update/uninstall path. See
[docs/product-contract.md](docs/product-contract.md) for the source of truth.

## Product Surface

- opens from `devsynapse`;
- reports the installed build with `devsynapse --version`;
- updates from `update-devsynapse`;
- removes local artifacts from `uninstall-devsynapse`;
- opens a single terminal UI for chat, setup, status and command execution;
- calls DeepSeek, OpenRouter, OpenCode Zen or OpenCode Go when a matching API key
  is configured;
- persists conversations, project registry data, task runs, model selection
  telemetry, procedural memories and skills in SQLite;
- executes local tool calls through `bash`, `read`, `glob`, `grep`, `edit` and
  `write` with command validation and project scoping;
- tracks token usage and estimated LLM cost from provider responses;
- keeps setup and operations in slash commands inside the TUI.

Not product surface:

- `devsynapse providers`, `devsynapse connect`, `devsynapse tui` or other
  external operator subcommands;
- shell aliases as the command installation mechanism;
- web or desktop entry points;
- disconnected prototype screens or generated runtime files.

## Requirements

- Python 3.10 or newer; CI/development currently uses Python 3.13.
- Linux or another Unix-like shell environment for the installer scripts.
- At least one provider API key:
  `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OPENCODE_ZEN_API_KEY` or
  `OPENCODE_GO_API_KEY`.

## Quick Start

Install or refresh the local app:

```bash
curl -fsSL https://raw.githubusercontent.com/N1ghthill/devsynapse-ai/main/scripts/install.sh | bash
```

Then reload your shell path and start the TUI:

```bash
source ~/.bashrc
devsynapse
```

The installer bootstraps the source checkout when needed, creates `venv/`,
installs dependencies, applies migrations and writes real commands to
`~/.local/bin`: `devsynapse`, `update-devsynapse` and `uninstall-devsynapse`.
It also removes previous DevSynapse aliases from shell rc files. Piped installs
use default setup values automatically; configure provider keys later with
`/connect` inside the TUI. For scripted local installs, set
`DEVSYNAPSE_ASSUME_DEFAULTS=1` to skip prompts explicitly.

From an existing checkout, the same contract is:

```bash
bash scripts/install.sh
devsynapse
```

Verify the installed build:

```bash
devsynapse --version
```

Update or remove:

```bash
update-devsynapse
uninstall-devsynapse
```

For development:

```bash
python3 -m venv venv
source venv/bin/activate
make install-dev
```

Configure a provider key inside the TUI:

```bash
devsynapse
```

Then run `/connect` and choose DeepSeek, OpenRouter, OpenCode Zen or OpenCode Go.
The setup form saves the API key, the provider's default model, and the default
provider route in the per-user runtime config. Manual config editing is still
available for scripted setups:

```bash
mkdir -p ~/.config/devsynapse-ai
cp .env.example ~/.config/devsynapse-ai/.env
$EDITOR ~/.config/devsynapse-ai/.env
```

Start DevSynapse:

```bash
devsynapse
```

## Canonical Flow

`devsynapse` opens the terminal UI. That is the only supported operator flow.
Provider setup, status, usage, budget, model selection, project selection and shell-tool
commands are slash commands inside the TUI. External subcommands such as
`devsynapse providers`, `devsynapse connect ...` or `devsynapse tui` are
intentionally rejected so the product has one clear entry point.

Inside the TUI, DevSynapse exposes operational slash commands:

```text
/connect                         open provider setup
/connect <provider>              open setup with provider selected
/connect <provider> <api-key>    save DeepSeek/OpenRouter/OpenCode keys
/providers                       show configured provider status
/discover                        refresh the model catalog
/model                           search and select active model
/models [provider]               list known models and pricing
/copy                            copy last assistant answer
/budget                          show daily/monthly plan usage
/budget daily|monthly <usd>      set budget limits
/router                          show manual model status
/usage                           show recent model/cost telemetry
/theme [theme] [layout]          show or change TUI appearance
!<command>                       run a shell command as a tool result
```

The TUI keeps the conversation log, input line, session state, provider status,
budget state and common commands visible in one terminal screen. The status bar
shows the trusted local approval mode, session token/cost totals, effective cwd,
project, session ID and budget health. The right panel summarizes the active
session, selected model, 24h request/token/cost telemetry, cache rate, error
rate, latency, budget usage, active project file changes and the top recent
model. The sidebar panels (Model, Telemetry) are collapsible for a cleaner view.
Shell outputs that look like unified diffs, git patches, JSON, YAML, CSV or TSV
are rendered with richer formatting; diffs also include a compact
file/hunk/add/remove summary.

Typing `/` opens contextual command suggestions; `Up` and `Down` move through
suggestions, and `Tab` or `Enter` completes the highlighted command or
argument. `Ctrl+P` opens the command palette for fuzzy command search.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+H` | Show help overlay |
| `F2` | Open model picker |
| `F3` | Copy last assistant answer |
| `F4` | Toggle model sidebar panel |
| `F5` | Toggle telemetry sidebar panel |
| `Ctrl+N` | New conversation |
| `Ctrl+L` | Clear chat |
| `Ctrl+P` | Open command palette |
| `Ctrl+R` | Refresh status |
| `Ctrl+Space` | Command menu |
| `Shift+Enter` | New line in input |
| `Up/Down` | Navigate command history |
| `Tab` | Autocomplete |

## Runtime State

By default DevSynapse stores user runtime files outside the source checkout:

- config: `~/.config/devsynapse-ai/.env`
- TUI preferences: `~/.config/devsynapse-ai/ui.json`
- SQLite data: `~/.local/share/devsynapse-ai/data/devsynapse_memory.db`
- logs: `~/.local/state/devsynapse-ai/logs/devsynapse.log`
- default source checkout for curl installs:
  `~/.local/share/devsynapse-ai/source`

Set `DEVSYNAPSE_HOME=/path/to/runtime` to keep config, data and logs together
under one directory. The more specific `DEVSYNAPSE_CONFIG_FILE`,
`DEVSYNAPSE_DATA_DIR` and `DEVSYNAPSE_LOGS_DIR` variables can override each path.
Set `ASSISTANT_USER_NAME` in the runtime config or environment to personalize
the system prompt; the default prompt is generic for distributed installs.
Set `LLM_STREAMING_ENABLED=false` to force non-streaming provider responses.
Set `LLM_DEFAULT_PROVIDER` to `deepseek`, `openrouter`, `opencode-zen` or
`opencode-go` to choose the first provider the router should prefer when more
than one key is configured. Provider model defaults can be set with
`DEEPSEEK_MODEL`, `OPENROUTER_MODEL`, `OPENCODE_ZEN_MODEL` and
`OPENCODE_GO_MODEL`. OpenRouter defaults to `openrouter/free` so normal chat can
use the free model router; `/model` lets operators switch to a specific free or
paid model with search.

TUI appearance is loaded from `ui.json`. Supported values are
`"theme": "dark" | "light" | "dracula"` and
`"layout": "default" | "dense"`. `DEVSYNAPSE_TUI_THEME`,
`DEVSYNAPSE_TUI_LAYOUT` and `DEVSYNAPSE_TUI_CONFIG_FILE` can override the JSON
file for temporary sessions. Inside the TUI, `/theme dracula dense` updates the
same preference file.

Runtime loaders create these files on a best-effort basis. Read-only runtime
config should not break commands such as `devsynapse --help`; commands that need
persistent memory still require a writable SQLite data directory.

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
core/              LLM orchestration, model selection, memory, plugins and tools
core/memory/       SQLite-backed stores
plugins/           local plugin examples
scripts/           install, update, migration and evaluation utilities
tests/             unit and integration tests
docs/              contributor and architecture documentation
```

## Verification

Product-critical checks:

```bash
make script-check
make tui-smoke
./venv/bin/pytest -q tests/integration/test_install_uninstall_scripts.py
./venv/bin/pytest -q tests/unit/test_cli.py tests/unit/test_cli_entry.py tests/unit/test_tui_smoke.py
```
