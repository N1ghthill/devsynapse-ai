# Contributor Onboarding

This guide is the shortest reliable path for a first-time contributor.

## Prerequisites

- Python `3.13`
- Node.js `22`
- `npm`
- `git`
- Linux with `bash`; the supported installer target is Debian/Ubuntu or a close
  derivative with `apt`

Native Windows setup is not currently validated. Windows users should prefer
WSL2 with Ubuntu/Debian for the supported path. The Python/FastAPI backend and
browser UI may run manually on Windows, but there is no tested PowerShell or
`.bat` installer yet, and shell aliases, path handling and command execution
semantics should be considered experimental there.

## Fresh Clone Setup

Recommended one-command setup:

```bash
bash scripts/install.sh
```

The installer checks system dependencies, creates the Python venv, installs frontend
and backend packages, configures the per-user runtime config (asks for your
DeepSeek API key and repositories directory interactively), runs database migrations, seeds the admin
user, builds the frontend, and registers the `devsynapse`, `update-devsynapse`
and `uninstall-devsynapse` shell aliases.

Packaged desktop installs do not run the shell installer. They use the in-app
Setup flow on first launch to collect the local admin password, DeepSeek API key
and default repository folder.

The project list is a registry in the local SQLite database. Setup registers
Git repositories discovered under the selected repository folder, but normal
chat/project pickers hide entries whose directories no longer exist. Admins can
open Admin > Projects to see stale entries marked as missing and remove only the
registry row; this does not delete any project files.

After install, reload your shell and launch:

```bash
source ~/.bashrc
devsynapse
```

## Updating Later

After the first install, update without repeating the interactive setup prompts:

```bash
devsynapse update
```

or:

```bash
update-devsynapse
```

The updater preserves runtime config, creates a backup of existing runtime files
when present, applies migrations, ensures missing seeded users without
overwriting existing passwords and rebuilds the frontend.

For packaged desktop builds, uninstall through the operating system package
manager, for example `sudo apt remove devsynapse-ai` for the `.deb` package or
the Windows Apps settings entry for the NSIS install. Linux desktop packages run
a pre-remove hook that stops the tray app and backend sidecar before package
files are removed. Runtime config, databases and logs are user data and remain
until manually deleted.

### Manual alternative

```bash
git clone https://github.com/N1ghthill/devsynapse-ai.git
cd devsynapse-ai

python3 -m venv venv
source venv/bin/activate
make setup
```

Then edit the runtime config printed by `make setup` and set `DEEPSEEK_API_KEY`.
The default path is `~/.config/devsynapse-ai/.env`.

## First Verification Pass

These are the first checks a new contributor should run before making changes:

```bash
./venv/bin/pytest -q tests/integration/test_api_routes.py
make script-check
cd frontend && npm run lint && npm run build
```

If those pass, the local environment is usually in a good state for normal development.

For a broader repository check:

```bash
make verify
```

## Running The App

Recommended:

```bash
make dev
```

Default local URLs:

- frontend: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- health: `http://127.0.0.1:8000/health`

## Seeded Local Users

The local setup seeds one admin user by default. The installer prompts for this password during setup; change it immediately for any non-local environment.

- `admin` / value from `DEFAULT_ADMIN_PASSWORD` in the runtime config

To add a non-admin user, set `DEFAULT_USER_USERNAME` and `DEFAULT_USER_PASSWORD`
in the runtime config.

## Manual Server Commands

If you prefer separate terminals:

```bash
make run
```

```bash
cd frontend && npm run dev
```

## First Contribution Checklist

- read [../../README.md](../../README.md)
- read [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- read [../api/overview.md](../api/overview.md) if changing backend contracts
- read [../architecture/data-model.md](../architecture/data-model.md) if changing persistence
- update the nearest relevant documentation in the same change
- include tests or build evidence when behavior changes

## Clean Clone Validation

This guide was revalidated from a clean clone on `2026-04-25` with:

- backend dependency install in a new `venv`
- frontend dependency install with `npm install`
- `make migrate`
- `make seed-users`
- `./venv/bin/pytest -q tests/integration/test_api_routes.py`
- `make script-check`
- `cd frontend && npm run lint && npm run build`

That validation passed without requiring repo-local manual fixes.
