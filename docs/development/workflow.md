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

- `make setup`: install backend/frontend dependencies, create `.env` if missing, apply migrations and seed local users
- `make dev`: run backend and frontend dev servers together
- `make test`: run backend tests
- `make lint`: run Python lint checks with Ruff
- `make frontend-build`: build the frontend bundle
- `make verify`: lint, test and build in one pass
- `make seed-users`: ensure default users exist
- `make migrate`: apply all SQLite migrations
- `make migration-status`: inspect current schema versions

## Revalidated Public Onboarding

The contributor path was revalidated from a clean public clone on `2026-04-24` with:

- `python3 -m venv venv`
- `source venv/bin/activate`
- `make setup`
- `./venv/bin/pytest -q tests/integration/test_api_routes.py`
- `cd frontend && npm install && npm run build`

## User Administration

Examples:

```bash
./venv/bin/python scripts/manage_users.py seed-defaults
./venv/bin/python scripts/manage_users.py list
./venv/bin/python scripts/manage_users.py create --username alice --password change-me --role admin
```

This is intentionally simple and local-first. It is sufficient for current SQLite-backed environments and should later evolve into a more formal admin workflow if the product scope demands it.
