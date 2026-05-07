# Product Contract

DevSynapse AI is a local-first terminal coding agent. The product is the TUI
opened by `devsynapse`; everything else exists to install, update, remove,
test or support that TUI.

## Official Surface

User-facing shell commands:

```bash
devsynapse
devsynapse --version
update-devsynapse
uninstall-devsynapse
```

`devsynapse` opens the Textual TUI. It does not expose operational subcommands.
Provider setup, status, budgets, usage, model selection, workspaces and local
tool execution happen inside the TUI through slash commands.

DevSynapse exposes two agent modes in the TUI: Build for implementation work and
Plan for read-only analysis. `Tab` on an empty input toggles the mode; `/mode
build|plan` sets it explicitly.

`/project <name>` selects a registered workspace. `/project <path>` registers
and selects an existing directory inside the configured workspace or
repositories root, including directories that are not Git repositories.

Official TUI commands:

```text
/connect
/providers
/status
/mode
/projects
/project
/discover
/model
/models
/copy
/budget
/router
/usage
/details
/theme
/new
/clear
/help
!<command>
```

## Install Contract

Canonical install:

```bash
curl -fsSL https://raw.githubusercontent.com/N1ghthill/devsynapse-ai/main/scripts/install.sh | bash
```

Then reload the shell path and start the TUI:

```bash
source ~/.bashrc
devsynapse
```

The installer:

- bootstraps or refreshes the source checkout;
- creates `venv/` inside the checkout;
- installs runtime dependencies;
- creates runtime config, data and logs directories;
- applies SQLite migrations;
- writes executable wrappers to `~/.local/bin`;
- removes previous DevSynapse shell aliases from shell rc files;
- adds `~/.local/bin` to PATH when needed.

For `curl | bash`, installer prompts use default setup values automatically.
Provider keys are configured later inside the TUI with `/connect`. For scripted
local installs, `DEVSYNAPSE_ASSUME_DEFAULTS=1` skips prompts explicitly.

Installed wrappers:

```text
~/.local/bin/devsynapse
~/.local/bin/update-devsynapse
~/.local/bin/uninstall-devsynapse
```

The wrappers point at the installed checkout and export the selected runtime
config file. They are the only supported installed command mechanism.

## Runtime Contract

Default paths:

```text
~/.config/devsynapse-ai/.env
~/.config/devsynapse-ai/ui.json
~/.local/share/devsynapse-ai/data/devsynapse_memory.db
~/.local/state/devsynapse-ai/logs/devsynapse.log
~/.local/share/devsynapse-ai/source
```

`DEVSYNAPSE_HOME` relocates config, data and logs together. Specific path
overrides are supported through `DEVSYNAPSE_CONFIG_FILE`,
`DEVSYNAPSE_DATA_DIR`, `DEVSYNAPSE_LOGS_DIR`, `DEVSYNAPSE_BIN_DIR` and
`DEVSYNAPSE_INSTALL_DIR`. The TUI loads `ui.json` for theme/layout preferences
and accepts temporary overrides via `DEVSYNAPSE_TUI_THEME`,
`DEVSYNAPSE_TUI_LAYOUT` and `DEVSYNAPSE_TUI_CONFIG_FILE`.

## Version Contract

The product version is `1.0.0` and must stay aligned in:

```text
pyproject.toml
config/settings.py
```

`devsynapse --version` is the operator check that the installed command points
at the expected build.

## Out Of Product

These are intentionally not product surfaces:

- external operator subcommands such as `devsynapse providers` or
  `devsynapse connect`;
- separate web, API server or desktop entry points;
- shell aliases as the installed command mechanism;
- generated runtime artifacts committed to source control;
- disconnected UI prototypes, unused screens, theme files or tool-display
  experiments.

## Cleanup Standard

A product-ready checkout should have:

- no unreferenced UI prototype files;
- no `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.coverage` or `htmlcov/`
  in source control;
- no duplicated install paths in docs;
- no undocumented operator command;
- tests covering install, update, uninstall, CLI version/help and TUI smoke.
