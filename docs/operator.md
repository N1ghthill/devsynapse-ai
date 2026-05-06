# Operator Guide

DevSynapse AI is operated from one app command:

```bash
devsynapse
```

That command opens the Textual TUI. Setup, provider state, budget, model selection,
usage and shell-tool execution happen inside the TUI through slash commands.
External operator subcommands are not supported.

Operator command surface:

```bash
devsynapse
devsynapse --version
update-devsynapse
uninstall-devsynapse
```

## Install

Canonical install:

```bash
curl -fsSL https://raw.githubusercontent.com/N1ghthill/devsynapse-ai/main/scripts/install.sh | bash
```

Then reload your shell path and start the TUI:

```bash
source ~/.bashrc
devsynapse
```

From an existing project checkout:

```bash
bash scripts/install.sh
devsynapse
```

The installer bootstraps the source checkout when needed, creates a Python
virtual environment, installs runtime dependencies, creates runtime
config/data/log directories, applies SQLite migrations and writes executable
commands into `~/.local/bin`:

```text
devsynapse
update-devsynapse
uninstall-devsynapse
```

It also removes previous DevSynapse aliases from shell rc files so the command
path is unambiguous. When installed through `curl | bash`, prompts use default
values automatically so pasted follow-up commands are not consumed as setup
answers. Configure provider keys later with `/connect` inside the TUI. For
scripted local installs, set `DEVSYNAPSE_ASSUME_DEFAULTS=1` to skip prompts
explicitly.

Check the installed build:

```bash
devsynapse --version
```

## Product Boundaries

The following are intentionally unsupported:

- `devsynapse providers`, `devsynapse connect` or any other external operator
  subcommand;
- shell aliases as the install mechanism;
- repository-local runtime config, databases or logs;
- web, API server or desktop launcher surfaces.

## Runtime Files

Defaults:

- config: `~/.config/devsynapse-ai/.env`
- TUI preferences: `~/.config/devsynapse-ai/ui.json`
- data: `~/.local/share/devsynapse-ai/data/devsynapse_memory.db`
- logs: `~/.local/state/devsynapse-ai/logs/devsynapse.log`

Use `DEVSYNAPSE_HOME=/path/to/runtime` to keep config, data and logs together
under one directory.

The TUI preference file supports `"theme": "dark" | "light" | "dracula"`,
`"layout": "default" | "dense"`, chat log `max_lines` and persisted sidebar
panel collapse state. Use `DEVSYNAPSE_TUI_THEME`, `DEVSYNAPSE_TUI_LAYOUT`,
`DEVSYNAPSE_TUI_MAX_LINES` or `DEVSYNAPSE_TUI_CONFIG_FILE` for temporary
overrides. Inside the TUI, `/theme dracula dense` persists the same preference
change.

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

Typing `/` in the main input opens the command menu. `Up`/`Down` or `Ctrl+K`/`Ctrl+J`
move through suggestions, and `Tab` or `Enter` completes the highlighted command
or provider, budget, or project argument. `Esc` closes suggestions. `Ctrl+Space`
opens the same menu from an empty input.
The status bar shows the trusted local approval mode, session token/cost totals,
effective cwd, project, session ID and budget health. Long-running agent and
shell work also shows an elapsed progress ticker. The right panel updates as
requests run: it shows session state, active model, 24h requests/chats/tokens/cost,
cache rate, error rate, average latency, daily and monthly budget bars, and the
top recent model.

Supported provider names:

- `deepseek`
- `openrouter`
- `opencode-zen`
- `opencode-go`

## Daily Commands

```text
/help                            list TUI commands (opens overlay)
/status                          show runtime state
/projects                        list registered projects
/project <name>                  set active project
/project                         clear active project
/usage                           show recent token and cost telemetry
/budget                          show daily/monthly budget state
/theme [theme] [layout]          show or change TUI appearance
/budget daily|monthly <usd>      update budget limits
/model                           search and select active model
/copy                            copy last assistant answer
/router                          show manual model status
/discover                        refresh model catalog
/models [provider]               list known models
!<command>                       run a shell command through the command bridge
```

Shell output that looks like a unified diff, git patch, JSON, YAML, CSV or TSV
is rendered with richer formatting. JSON objects and arrays use a tree view,
CSV/TSV uses a table view, and diffs include a compact file, hunk, addition and
deletion summary.

When an active project is selected, the sidebar Files panel summarizes git
worktree changes and links the next inspection path to `!git diff`.

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
| `PageUp/PageDown` | Scroll chat log |
| `Ctrl+Home/Ctrl+End` | Jump to top/bottom of chat log |
| `Shift+Enter` | New line in input |
| `Up/Down`, `Ctrl+K/J` | Navigate command history or menu suggestions |
| `Tab` | Autocomplete |
| `Esc` | Close command suggestions/dialogs |

## Update

```bash
update-devsynapse
```

or:

```bash
bash scripts/update.sh
```

The updater backs up runtime files, refreshes the checkout when allowed, updates
Python dependencies, reapplies migrations and refreshes the command wrappers in
`~/.local/bin`. It does not build or start any web surface.

## Uninstall Local Artifacts

```bash
uninstall-devsynapse
```

The uninstaller removes installed command wrappers, previous shell aliases and
the local virtual environment, then asks whether to remove runtime data/logs and
config.
