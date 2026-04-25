# Contributor Onboarding

This guide is the shortest reliable path for a first-time contributor.

## Prerequisites

- Python `3.13`
- Node.js `22`
- `npm`
- `git`

## Fresh Clone Setup

Recommended one-command setup:

```bash
bash scripts/install.sh
```

The installer checks system dependencies, creates the Python venv, installs frontend
and backend packages, configures `.env` (asks for your DeepSeek API key and
repositories directory interactively), runs database migrations, seeds the admin
user, builds the frontend, and registers the `devsynapse` and `uninstall-devsynapse`
shell aliases.

After install, reload your shell and launch:

```bash
source ~/.bashrc
devsynapse
```

### Manual alternative

```bash
git clone https://github.com/N1ghthill/devsynapse-ai.git
cd devsynapse-ai

python3 -m venv venv
source venv/bin/activate
make setup
```

Then edit `.env` and set `DEEPSEEK_API_KEY`.

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

The local setup seeds one admin user by default. Change these credentials immediately for any non-local environment.

- `admin` / value from `DEFAULT_ADMIN_PASSWORD` in `.env` (default: `admin`)

To add a non-admin user, set `DEFAULT_USER_USERNAME` and `DEFAULT_USER_PASSWORD` in `.env`.

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

This guide was revalidated from a clean clone on `2026-04-24` with:

- backend dependency install in a new `venv`
- frontend dependency install with `npm install`
- `make migrate`
- `make seed-users`
- `./venv/bin/pytest -q tests/integration/test_api_routes.py`
- `cd frontend && npm run build`

That validation passed without requiring repo-local manual fixes.
