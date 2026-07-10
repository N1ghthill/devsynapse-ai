# Development Workflow

This workflow covers the current Python core and transitional TUI. Desktop
changes must also follow
[the desktop foundation implementation plan](desktop-foundation.md) and add the
frontend, Rust, IPC and package checks required by their roadmap phase.

## Local Loop

```bash
python3 -m venv venv
source venv/bin/activate
make install-dev
make migrate
make verify
```

For first-time setup from a new clone, use [onboarding.md](onboarding.md).

## Standard Commands

- `make setup`: create `venv`, install runtime dependencies and apply migrations.
- `make install`: install runtime dependencies from `requirements.txt`.
- `make install-dev`: install runtime and test dependencies from
  `requirements-dev.txt`.
- `make test`: run pytest.
- `make lint`: run Ruff.
- `make script-check`: check shell script syntax, compile Python scripts and run
  ShellCheck when installed.
- `make tui-smoke`: check TUI launcher help.
- `make verify`: run lint, tests, script checks and TUI smoke checks.
- `make migrate`: apply SQLite migrations.
- `make migration-status`: inspect current migration state.
- `make eval-agent`: run the disposable agent evaluation harness.

## Running The Agent

Start the TUI:

```bash
devsynapse
```

For an uninstalled checkout, run `./venv/bin/python -m devsynapse.cli`.

Useful TUI commands:

- `/connect <provider> <api-key>` saves provider keys in runtime config.
- `/providers` shows key status without printing full secrets.
- `/discover` refreshes the model catalog for configured providers.
- `/model` opens searchable model selection for the active provider.
- `/models [provider]` lists known models with context and pricing data.
- `/copy` copies the last assistant answer to the clipboard.
- `/budget` shows daily/monthly usage against configured limits.
- `/router` shows manual model status.
- `/usage` shows recent token, cache, cost and model telemetry.
- `!<command>` runs a shell command through the constrained command bridge.

The TUI keeps session, provider, budget and command context visible beside the
chat.

## Dependency Manifests

- `requirements.txt`: runtime dependencies for installer and launcher scripts.
- `requirements-dev.txt`: development and test dependencies.
- `requirements.lock` / `requirements-dev.lock`: pinned constraints used by
  Makefile and install/update scripts when present.
- `pyproject.toml`: package metadata and `devsynapse` console script.

Keep `requirements.txt` and `pyproject.toml` aligned when runtime imports
change.

## Runtime Configuration During Development

Use `DEVSYNAPSE_HOME` for isolated local runs:

```bash
DEVSYNAPSE_HOME=/tmp/devsynapse-dev ./venv/bin/python -m devsynapse.cli --help
```

The settings loader tolerates read-only config files for non-runtime commands,
but memory-backed agent work requires a writable data directory.

## Legacy Agent Completion Guard

Automatic execution keeps a lightweight checklist for implementation requests.
When the prompt explicitly names files such as `pyproject.toml`, `README.md` or
`src/app.py`, or asks for `pytest`, the brain tracks successful write commands
and passing pytest output before accepting a final response. If the model emits
completion prose before the checklist is complete, the brain feeds back the
missing items and asks for one next tool call.

This guard belongs to the transitional generic command loop. Do not extend it
to implement new repository workflows. New work should use registered typed
operations and phase-specific acceptance criteria from
[the repository operations roadmap](../roadmap.md).
