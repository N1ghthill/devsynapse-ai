# Operator Guide

DevSynapse AI is operated from one terminal command:

```bash
devsynapse
```

That command opens the Textual TUI. Setup, provider state, budget, model selection,
usage and shell-tool execution happen inside the TUI through slash commands.
External operator subcommands are not supported.

## Install

From the project checkout:

```bash
bash scripts/install.sh
source ~/.bashrc
devsynapse
```

The installer creates a Python virtual environment, installs runtime
dependencies, creates runtime config/data/log directories, applies SQLite
migrations and writes shell aliases.

## Runtime Files

Defaults:

- config: `~/.config/devsynapse-ai/.env`
- data: `~/.local/share/devsynapse-ai/data/devsynapse_memory.db`
- logs: `~/.local/state/devsynapse-ai/logs/devsynapse.log`

Use `DEVSYNAPSE_HOME=/path/to/runtime` to keep config, data and logs together
under one directory.

## First Provider

Inside the TUI:

```text
/connect
/connect deepseek <api-key>
/providers
/status
```

`/connect` opens the provider setup form. Choose the server, paste the API key,
and keep or edit the default model. The selected server becomes
`LLM_DEFAULT_PROVIDER` for manual model control.
OpenRouter defaults to `openrouter/free` for normal chat. Use `/model` to search
the refreshed principal catalog and choose a specific free or paid model.

Supported provider names:

- `deepseek`
- `openrouter`
- `opencode-zen`
- `opencode-go`

## Daily Commands

```text
/help                            list TUI commands
/status                          show runtime state
/projects                        list registered projects
/project <name>                  set active project
/project                         clear active project
/usage                           show recent token and cost telemetry
/budget                          show daily/monthly budget state
/budget daily|monthly <usd>      update budget limits
/model                           search and select active model
/router                          show manual model status
/discover                        refresh model catalog
/models [provider]               list known models
!<command>                       run a shell command through the command bridge
```

## Update

```bash
update-devsynapse
```

or:

```bash
bash scripts/update.sh
```

The updater backs up runtime files, refreshes the checkout when allowed, updates
Python dependencies and applies migrations. It does not build or start any web
surface.

## Uninstall Local Artifacts

```bash
uninstall-devsynapse
```

The uninstaller removes shell aliases and the local virtual environment, then
asks whether to remove runtime data/logs and config.
