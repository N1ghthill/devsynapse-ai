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
Provider setup, status, budgets, usage, model selection, projects and local
tool execution happen inside the TUI through slash commands.

Official TUI commands:

```text
/connect
/providers
/status
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
/new
/clear
/help
!<command>
```

## Install Contract

Canonical install:

```bash
curl -fsSL https://raw.githubusercontent.com/N1ghthill/devsynapse-ai/main/scripts/install.sh | bash
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
~/.local/share/devsynapse-ai/data/devsynapse_memory.db
~/.local/state/devsynapse-ai/logs/devsynapse.log
~/.local/share/devsynapse-ai/source
```

`DEVSYNAPSE_HOME` relocates config, data and logs together. Specific path
overrides are supported through `DEVSYNAPSE_CONFIG_FILE`, `DEVSYNAPSE_DATA_DIR`,
`DEVSYNAPSE_LOGS_DIR`, `DEVSYNAPSE_BIN_DIR` and `DEVSYNAPSE_INSTALL_DIR`.

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
