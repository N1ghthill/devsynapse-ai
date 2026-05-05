# Contributor Onboarding

This guide describes the current TUI-first checkout.

## Prerequisites

- Python 3.10 or newer; local development currently uses Python 3.13.
- `bash`, `git` and a Unix-like shell environment for the installer scripts.
- At least one LLM provider API key for real agent use.

## Fresh Clone Setup

```bash
git clone https://github.com/N1ghthill/devsynapse-ai.git
cd devsynapse-ai

python3 -m venv venv
source venv/bin/activate
make install-dev
make migrate
```

Create or edit the runtime config:

```bash
mkdir -p ~/.config/devsynapse-ai
cp .env.example ~/.config/devsynapse-ai/.env
$EDITOR ~/.config/devsynapse-ai/.env
```

Set at least one of:

- `DEEPSEEK_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENCODE_ZEN_API_KEY`
- `OPENCODE_GO_API_KEY`

## Running The App

Start the terminal UI:

```bash
./devsynapse.sh
```

Use slash commands inside the TUI:

```text
/connect deepseek <api-key>
/providers
/status
/usage
/budget
/router
```

The TUI shows chat, active session, provider state, budget state and command
hints in one terminal screen.

## Runtime Files

Defaults:

- config: `~/.config/devsynapse-ai/.env`
- SQLite data: `~/.local/share/devsynapse-ai/data/devsynapse_memory.db`
- logs: `~/.local/state/devsynapse-ai/logs/devsynapse.log`

For disposable development runs, set `DEVSYNAPSE_HOME`:

```bash
DEVSYNAPSE_HOME=/tmp/devsynapse-dev ./venv/bin/python -m devsynapse.cli --help
```

## First Verification Pass

```bash
make lint
make test
make script-check
make tui-smoke
```

For the standard combined check:

```bash
make verify
```

## Contribution Checklist

- read [../../README.md](../../README.md);
- read [../architecture/overview.md](../architecture/overview.md) before
  changing runtime boundaries;
- read [../architecture/data-model.md](../architecture/data-model.md) before
  changing persistence;
- update nearby documentation when behavior, setup, migrations or runtime
  configuration changes;
- include focused tests for changed behavior.
