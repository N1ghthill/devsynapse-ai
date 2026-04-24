# DevSynapse AI

[![CI](https://github.com/N1ghthill/devsynapse-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/N1ghthill/devsynapse-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

DevSynapse AI is an open source development assistant that combines:
- project-aware technical chat;
- persistent memory for conversations, preferences and projects;
- controlled command execution with explicit authorization boundaries;
- operational visibility through monitoring, usage tracking, budget thresholds and alerts.

The repository is organized for contributors, not only for local use. Backend contracts, frontend behavior, persistence and runtime workflows are documented and versioned in-repo.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Verified Baseline

Documentation refresh validated on `2026-04-24`:
- backend test suite: `106 passed`
- frontend production build: passed
- local API + frontend integration validated manually during development
- public onboarding flow revalidated from a clean clone with fresh dependency installs, migrations, seeded users, route-level test pass and frontend build
- LLM usage telemetry, conversation persistence, execution workflow and dashboard metrics are active in the current codebase

## What The Project Does

DevSynapse AI provides:
- a FastAPI backend for auth, chat, command execution, monitoring, settings and admin flows;
- a React/Vite frontend with chat, dashboard, settings and admin interfaces;
- SQLite-backed persistence for runtime state and migration-controlled schema evolution;
- an LLM orchestration layer with command extraction and fallback behavior;
- a constrained execution bridge for `bash`, `read`, `glob`, `grep`, `edit` and `write`;
- per-user, project-scoped mutation authorization for non-admin users;
- token and cost telemetry for LLM usage.
- configurable daily/monthly LLM budgets with warning and critical thresholds.

## Repository Map

```text
devsynapse-ai/
├── api/                    # FastAPI application, contracts and routes
├── config/                 # Centralized settings and policy constants
├── core/                   # Brain, auth, memory, monitoring, bridge, plugins
├── docs/                   # Contributor-facing technical documentation
├── frontend/               # React/Vite operator UI
├── plugins/                # Plugin implementations
├── scripts/                # Local operational utilities
├── tests/                  # Unit and integration tests
├── data/                   # SQLite databases (generated locally)
├── logs/                   # Runtime logs (generated locally)
├── .env.example            # Runtime configuration template
├── Makefile                # Common dev commands
└── README_PROFESSIONAL.md  # Engineering-oriented companion doc
```

## Quick Start

Before you start, see the contributor-focused setup path in [docs/development/onboarding.md](docs/development/onboarding.md).

### Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
make migrate
make seed-users
make run
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Local URLs

- frontend: `http://127.0.0.1:5173`
- OpenAPI docs: `http://127.0.0.1:8000/docs`
- health endpoint: `http://127.0.0.1:8000/health`

### Screenshots

Curated product screenshots are available in [docs/screenshots/README.md](docs/screenshots/README.md).

## Main Development Commands

```bash
make test
make lint
make frontend-build
make verify
make migrate
make migration-status
```

## Documentation Index

Start here:
- contributor guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- security policy: [SECURITY.md](SECURITY.md)
- changelog: [CHANGELOG.md](CHANGELOG.md)
- documentation index: [docs/README.md](docs/README.md)

Technical guides:
- contributor onboarding: [docs/development/onboarding.md](docs/development/onboarding.md)
- architecture overview: [docs/architecture/overview.md](docs/architecture/overview.md)
- persistence and data model: [docs/architecture/data-model.md](docs/architecture/data-model.md)
- API overview: [docs/api/overview.md](docs/api/overview.md)
- development workflow: [docs/development/workflow.md](docs/development/workflow.md)
- testing guide: [docs/development/testing.md](docs/development/testing.md)
- runtime and delivery notes: [docs/deployment/runtime.md](docs/deployment/runtime.md)

Supplementary references:
- engineering guide: [README_PROFESSIONAL.md](README_PROFESSIONAL.md)
- frontend guide: [frontend/README.md](frontend/README.md)

## Roadmap

Near-term priorities:
- stronger explicit project attribution across assistant flows
- budget and spend alerts for LLM usage
- clearer operational dashboards and reporting
- deeper API and integration coverage
- contributor ergonomics for issues, pull requests and release notes

## Contribution Scope

Contributions are welcome for:
- bug fixes and reliability improvements
- documentation quality and contributor ergonomics
- monitoring, telemetry and operational maturity
- frontend UX improvements that preserve current backend contracts
- security hardening and test coverage expansion

Before opening a PR, read [CONTRIBUTING.md](CONTRIBUTING.md).
For the shortest setup path from a new clone, read [docs/development/onboarding.md](docs/development/onboarding.md).

## Security Boundary

This project executes constrained development-oriented commands, but it is not a full sandbox product. The repository should be described as a safer local execution framework, not as a formally hardened isolation system. See [SECURITY.md](SECURITY.md).
