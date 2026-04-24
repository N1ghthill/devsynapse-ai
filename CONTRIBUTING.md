# Contributing to DevSynapse AI

## Principles

Contributions should improve one or more of these areas:
- correctness
- security posture
- operational clarity
- documentation quality
- contributor experience

This repository favors explicit contracts and verifiable behavior over implicit assumptions.

## Before You Start

1. Read [README.md](README.md).
2. Read [docs/README.md](docs/README.md).
3. Check whether your change affects:
   - API contracts
   - authorization behavior
   - persistence schema
   - contributor workflows
4. If it does, update documentation in the same change.

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
make migrate
make seed-users
```

Frontend:

```bash
cd frontend
npm install
```

## Development Workflow

Recommended backend loop:

```bash
make lint
make test
```

Full repository verification:

```bash
make verify
```

If you changed migrations or persistence logic:

```bash
make migration-status
make migrate
```

## Pull Request Expectations

A good PR should:
- state the problem clearly
- explain the chosen approach
- describe user-visible behavior changes
- mention updated documentation
- mention validation performed

Include evidence when relevant:
- test output
- frontend build result
- API contract examples
- screenshots for UI changes if you have them available

## Documentation Standard

Documentation is required when you change:
- route contracts
- persistence schema
- setup commands
- permissions or security behavior
- dashboard/telemetry semantics
- contributor workflow

At minimum, update the nearest relevant file under `docs/` or the root `README`.

## Coding Expectations

- preserve current backend/frontend contracts unless intentionally changing them
- prefer explicit types and small, readable changes
- keep authorization logic conservative
- do not claim production-grade security where it does not exist
- do not introduce secrets into source-controlled files

## Tests

Run the relevant tests before submitting:

```bash
./venv/bin/pytest -q
cd frontend && npm run build
```

At the time of the latest documentation refresh, local verification produced `106` passing backend tests and a successful frontend production build.

## Scope Notes

This repository is open source, but not every direction is equally useful. High-value contributions usually fall into:
- reliability fixes
- schema and migration safety
- test coverage
- docs and onboarding quality
- monitoring and operational maturity
- frontend clarity without contract drift
