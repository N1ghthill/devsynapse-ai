# Development Workflow

## Local Loop

Recommended sequence:

```bash
python3 -m venv venv
source venv/bin/activate
make setup
make verify
make dev
```

For first-time setup from a new public clone, use [onboarding.md](onboarding.md).

For frontend development:

```bash
cd frontend
npm install
npm run dev
```

## Standard Commands

- `make setup`: install backend/frontend dependencies, create the per-user runtime config if missing, apply migrations and seed local users
- `make dev`: run backend and frontend dev servers together
- `make test`: run backend tests
- `make lint`: run Python lint checks with Ruff
- `make script-check`: run shell syntax checks, Python script compilation and ShellCheck when installed
- `make frontend-lint`: run frontend ESLint
- `make frontend-build`: build the frontend bundle
- `make desktop-backend`: build the PyInstaller backend sidecar for Tauri
- `make desktop-dev`: build the sidecar and run the Tauri app in dev mode
- `make desktop-build`: build the sidecar and generate default desktop packages
- `make verify`: run Python lint, backend tests, script checks, frontend lint and frontend build in one pass
- `make ui-smoke`: build and smoke-test the served UI with Playwright against temporary local databases and seeded smoke users
- `make update`: update code, refresh dependencies, apply migrations and rebuild the frontend for an existing install
- `make update-locks`: regenerate Python dependency lock constraints from the manifests
- `make seed-users`: ensure default users exist
- `make migrate`: apply all SQLite migrations
- `make migration-status`: inspect current schema versions

Python dependency manifests are split by purpose:
- `requirements.txt`: runtime dependencies
- `requirements-dev.txt`: development and test dependencies
- `requirements.lock` / `requirements-dev.lock`: resolved constraints used by Makefile and CI when installing

Dependabot watches GitHub Actions, Python, frontend npm and Tauri Cargo manifests weekly. The `Dependency Locks` workflow also runs weekly and can be dispatched manually to regenerate Python lock constraints and open a pull request when they change.

GitHub Releases are published from pushed `v*.*.*` tags by reading `docs/releases/<tag>.md`. Create the release notes before pushing the tag; manual dispatch is available for an existing tag.

Desktop artifacts for landing-page downloads are tracked in
[../deployment/desktop-distribution.md](../deployment/desktop-distribution.md).

## Updating An Existing Install

Installed users should prefer the updater instead of rerunning the interactive installer:

```bash
devsynapse update
```

The installer also creates a direct alias:

```bash
update-devsynapse
```

For a specific published release:

```bash
devsynapse update --version v0.6.0
```

The updater backs up existing runtime files when present, preserves runtime
configuration, refreshes Python/frontend dependencies, applies migrations,
ensures missing seeded users and rebuilds the production frontend bundle.

## Revalidated Public Onboarding

The contributor path was revalidated from a clean public clone on `2026-04-25` with:

- `python3 -m venv venv`
- `source venv/bin/activate`
- `make setup`
- `./venv/bin/pytest -q tests/integration/test_api_routes.py`
- `make script-check`
- `cd frontend && npm install && npm run lint && npm run build`

## User Administration

Examples:

```bash
./venv/bin/python scripts/manage_users.py seed-defaults
./venv/bin/python scripts/manage_users.py list
./venv/bin/python scripts/manage_users.py create --username alice --password change-me --role admin
```

This is intentionally simple and local-first. It is sufficient for current SQLite-backed environments and should later evolve into a more formal admin workflow if the product scope demands it.
