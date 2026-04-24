# Contributor Onboarding

This guide is the shortest reliable path for a first-time contributor.

## Prerequisites

- Python `3.13`
- Node.js `22`
- `npm`
- `git`

## Fresh Clone Setup

```bash
git clone https://github.com/N1ghthill/devsynapse-ai.git
cd devsynapse-ai

python3 -m venv venv
source venv/bin/activate
./venv/bin/pip install -r requirements-dev.txt

cp .env.example .env
make migrate
make seed-users

cd frontend
npm install
cd ..
```

## First Verification Pass

These are the first checks a new contributor should run before making changes:

```bash
./venv/bin/pytest -q tests/integration/test_api_routes.py
cd frontend && npm run build
```

If those pass, the local environment is usually in a good state for normal development.

For a broader repository check:

```bash
make verify
```

## Running The App

Backend:

```bash
make run
```

Frontend:

```bash
cd frontend
npm run dev
```

Default local URLs:

- frontend: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- health: `http://127.0.0.1:8000/health`

## Seeded Local Users

The local setup seeds two users by default. Change these immediately for any non-local environment.

- `admin` / value from `DEFAULT_ADMIN_PASSWORD` in `.env`
- `irving` / value from `DEFAULT_USER_PASSWORD` in `.env`

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
