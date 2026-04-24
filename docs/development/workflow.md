# Development Workflow

## Local Loop

Recommended sequence:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
make migrate
make verify
make run
```

For frontend development:

```bash
cd frontend
npm install
npm run dev
```

## Standard Commands

- `make test`: run backend tests
- `make lint`: run Python lint checks with Ruff
- `make frontend-build`: build the frontend bundle
- `make verify`: lint, test and build in one pass
- `make seed-users`: ensure default users exist
- `make migrate`: apply all SQLite migrations
- `make migration-status`: inspect current schema versions

## User Administration

Examples:

```bash
./venv/bin/python scripts/manage_users.py seed-defaults
./venv/bin/python scripts/manage_users.py list
./venv/bin/python scripts/manage_users.py create --username alice --password change-me --role admin
```

This is intentionally simple and local-first. It is sufficient for current SQLite-backed environments and should later evolve into a more formal admin workflow if the product scope demands it.
