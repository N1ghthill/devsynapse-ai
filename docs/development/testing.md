# Testing Guide

## Current Verification Baseline

At the latest documentation refresh on `2026-04-25`, local verification produced:
- `143` passing backend tests
- successful script checks
- successful frontend lint and production build
- passing installer/updater/uninstaller and development-server smoke tests
- browser UI smoke coverage for login, dashboard, settings save and admin navigation

## Test Layout

```text
tests/
├── unit/
└── integration/
```

### Unit tests

Main areas covered:
- `brain` behavior and command extraction
- `memory` persistence and telemetry
- `opencode bridge` validation and authorization
- plugin system basics

### Integration tests

Main areas covered:
- route-level API contract validation
- command execution responses
- conversation flows and telemetry persistence

## Commands

Run all backend tests:

```bash
./venv/bin/pytest -q
```

Run a focused module:

```bash
./venv/bin/pytest -q tests/unit/test_memory.py
./venv/bin/pytest -q tests/unit/test_brain.py
./venv/bin/pytest -q tests/integration/test_api_routes.py
```

Run repository verification:

```bash
make verify
```

Script validation:

```bash
make script-check
```

`make script-check` always runs shell syntax checks and Python script compilation.
If `shellcheck` is installed locally, it also runs ShellCheck against the shell entrypoints,
including `scripts/update.sh`.

Frontend validation:

```bash
cd frontend
npm run lint
npm run build
```

Browser UI smoke:

```bash
make ui-smoke
```

`make ui-smoke` starts a temporary API with disposable SQLite databases, builds the
frontend with a matching API URL and runs Playwright against the production
bundle served by FastAPI. The smoke runtime seeds an admin account plus a
temporary non-admin user so the Admin permission workflow is exercised without
touching local developer data.

Install the Chromium browser once with:

```bash
cd frontend
npx playwright install chromium
```

Screenshot evidence:

```bash
cd frontend
npm run capture:docs-screenshots
```

The screenshot workflow requires a running backend and frontend with seeded local users. See [../screenshots/README.md](../screenshots/README.md).

## Expectations For Contributors

Add or update tests when you change:
- route payloads
- migration behavior
- execution authorization
- token/cost telemetry
- conversation persistence semantics

## Testing Philosophy

The repository currently emphasizes:
- small unit tests for logic-heavy services
- route-level integration tests for contract safety
- frontend build verification as a compatibility gate
- product screenshots as visual evidence for documented workflows

This is sufficient for the current local-first scope, but future contributors should continue expanding higher-confidence integration coverage where it adds real value.
