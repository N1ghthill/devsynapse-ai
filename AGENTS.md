# Repository Guidelines

## Project Structure & Architecture

DevSynapse AI is local-first FastAPI + React/Vite + SQLite. `api/` holds routes and request/response models; `core/` holds business logic, persistence, auth, monitoring, migrations, plugins, and command execution; `config/` holds settings. `frontend/src/` contains pages, components, API helpers, hooks, and shared types. Tests live in `tests/unit/` and `tests/integration/`; docs in `docs/`; scripts in `scripts/`; plugins in `plugins/`. Keep transport, core logic, persistence, and UI responsibilities separate.

## Documentation & Contract Discipline

Documentation is part of the runtime contract. If a change affects behavior, API fields, routes, auth, setup, migrations, telemetry, or operations, update the nearest relevant doc in the same change. The API contract is FastAPI OpenAPI plus `api/models.py`; keep `frontend/src/types.ts` and `frontend/src/api/client.ts` aligned. Schema changes require explicit migrations and data model docs.

## Build, Test, and Development Commands

Use the root `Makefile`:

- `make install-dev`: install Python dev dependencies.
- `make run`: start FastAPI on `127.0.0.1:8000`.
- `make lint`: run Ruff.
- `make test`: run pytest.
- `make frontend-build`: build the frontend.
- `make verify`: run lint, tests, and frontend build.
- `make migrate` / `make migration-status`: apply or inspect migrations.

For frontend development, run `cd frontend && npm install`, then `npm run dev`, `npm run lint`, or `npm run build`.

## Coding Style & Naming Conventions

CI uses Python `3.13`; Ruff targets `py310` syntax with 100-character lines, double quotes, space indentation, and import sorting. Keep modules small and explicit, especially around authorization, persistence, and command execution. Tests and Python modules use `snake_case`. React files use TypeScript and `.tsx`; prefer `PascalCase` components and typed API boundaries. Avoid cross-layer shortcuts or duplicated business rules.

## Testing Guidelines

Pytest discovers `test_*.py`, `Test*` classes, and `test_*` functions under `tests/`. Use markers (`unit`, `integration`, `slow`, `e2e`) when useful. Add or update tests for route contracts, migrations, authorization, telemetry, and persistence. Run focused tests such as `./venv/bin/pytest -q tests/unit/test_memory.py`.

## Commit & Pull Request Guidelines

Recent history uses prefixes such as `feat:`, `docs:`, and `chore:`; follow that pattern with concise, imperative summaries. Pull requests should state the problem, approach, validation performed, and documentation updates. Include screenshots for UI changes.

## Security & Configuration Tips

Start from `.env.example` and keep secrets out of commits. Treat local databases, logs, and runtime artifacts as disposable developer state. This project provides constrained local command execution, not a hardened sandbox; keep authorization changes conservative, project-aware, auditable, tested, and documented.
