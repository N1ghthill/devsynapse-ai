# DevSynapse AI: Engineering Guide

## Purpose

DevSynapse AI is a development assistant platform for technical workflows. Its role is to combine:
- DeepSeek-backed conversational assistance with project-aware context;
- persistent memory of interactions and preferences;
- controlled execution of development-oriented commands;
- operational visibility through monitoring and alerts.

This document describes the engineering baseline of the repository. It is intentionally narrower and more factual than a product pitch.

## System Overview

### Backend responsibilities

- expose HTTP routes for auth, chat, command execution, monitoring, settings and administration;
- orchestrate DeepSeek API requests and inject project/user context;
- persist conversation history, user state and runtime settings;
- validate and execute constrained file and shell operations;
- emit monitoring events and plugin lifecycle hooks.

### Frontend responsibilities

- authenticate users against the backend;
- provide chat, dashboard and settings interfaces;
- consume the backend contracts without duplicating business rules;
- surface operational status clearly.

## Current Runtime Design

### API layer

Files:
- [api/app.py](api/app.py)
- [api/server.py](api/server.py)
- [api/models.py](api/models.py)
- [api/dependencies.py](api/dependencies.py)
- [api/routes/auth.py](api/routes/auth.py)
- [api/routes/chat.py](api/routes/chat.py)
- [api/routes/monitoring.py](api/routes/monitoring.py)
- [api/routes/settings.py](api/routes/settings.py)
- [api/routes/admin.py](api/routes/admin.py)

Design choices:
- route modules are split by responsibility;
- shared service singletons live in `api/dependencies.py`;
- request/response contracts are centralized in `api/models.py`;
- `api/server.py` is only an execution entrypoint, not an application container.

### Core services

Files:
- [core/brain.py](core/brain.py)
- [core/auth.py](core/auth.py)
- [core/memory.py](core/memory.py)
- [core/opencode_bridge.py](core/opencode_bridge.py)
- [core/monitoring.py](core/monitoring.py)
- [core/plugin_system.py](core/plugin_system.py)

Responsibilities:
- `brain.py`: prompt assembly, DeepSeek invocation with native tool calling (strict mode, thinking mode), result interpretation;
- `auth.py`: password hashing, JWT issuance and token validation;
- `memory.py`: SQLite persistence for conversations, preferences, users, runtime settings and admin audit events;
- `opencode_bridge.py`: command parsing, path validation and constrained execution;
- `monitoring.py`: command/API telemetry and alert lifecycle;
- `plugin_system.py`: extension hooks across major lifecycle points.

### Persistence model

Current storage is SQLite-based and adequate for local and early staged environments.

Primary persisted concepts:
- conversations
- user preferences
- projects
- decisions
- users
- app settings
- project permissions
- administrative audit logs
- command execution telemetry
- API usage telemetry
- alerts

This is sufficient for a disciplined local system, but not yet a substitute for a production-grade migration and multi-tenant data model.

Schema evolution is now versioned through:
- [core/db.py](core/db.py)
- [core/migrations.py](core/migrations.py)
- [scripts/migrate.py](scripts/migrate.py)

## Configuration Strategy

Configuration is centralized in [config/settings.py](config/settings.py).

Principles:
- environment variables define runtime behavior;
- code should not contain deploy-specific secrets;
- operational installs store config, SQLite databases and logs outside the source checkout by default;
- stable policy constants may stay in code when they are part of the trusted baseline;
- mutable operational settings are persisted through the app settings table when appropriate.

Bootstrap reference:
- [`.env.example`](.env.example)

Default runtime locations:
- config: `~/.config/devsynapse-ai/.env`
- SQLite data: `~/.local/share/devsynapse-ai/data`
- logs: `~/.local/state/devsynapse-ai/logs`

Set `DEVSYNAPSE_HOME` to keep those paths under one custom runtime directory, or
set `DEVSYNAPSE_CONFIG_FILE`, `DEVSYNAPSE_DATA_DIR` and `DEVSYNAPSE_LOGS_DIR`
individually.

## Security Posture

### What is already improved

- credentials are no longer represented only as in-memory hardcoded users;
- JWT signing is environment-driven;
- command execution now avoids `shell=True` for direct bash execution;
- command validation is stricter than the earlier POC baseline;
- command authorization is role-aware, separating inspection from mutating actions;
- mutation permission for non-admin users can now be scoped per user and per project;
- administrative permission updates now leave an audit trail;
- authentication is represented as a service, not scattered helper code.

### What is still not complete

- command execution is not yet full sandboxing;
- RBAC is still minimal;
- there is no formal secrets rotation workflow;
- CI is still baseline-level and should grow with integration depth.

The correct engineering framing is “safer foundation”, not “production-complete security”.

## API Surface

Primary routes:
- `POST /auth/login`
- `GET /auth/verify`
- `POST /chat`
- `GET /chat/history`
- `POST /execute`
- `POST /feedback`
- `GET /health`
- `GET /monitoring/health`
- `GET /monitoring/stats`
- `GET /monitoring/alerts`
- `POST /monitoring/alerts/{id}/resolve`
- `GET /settings`
- `PUT /settings`
- `GET /admin/users`
- `PUT /admin/users/{username}/permissions`
- `GET /admin/audit-logs`

The canonical live contract remains the OpenAPI spec exposed by FastAPI at `/docs`.

## Frontend Integration Notes

The frontend is no longer expected to guess backend response shapes. It has been aligned to the actual contracts and should treat the backend as the single source of truth for:
- auth token semantics;
- route protection and session validation;
- chat response metadata;
- monitoring payload shape;
- persisted settings shape;
- administrative user-permission state.

Related files:
- [frontend/src/api/client.ts](frontend/src/api/client.ts)
- [frontend/src/types.ts](frontend/src/types.ts)
- [frontend/src/hooks/useAuth.ts](frontend/src/hooks/useAuth.ts)

## Development Workflow

### Platform Support

The supported release installation path is Linux on Debian/Ubuntu or close
`apt`-based derivatives. The repository's installer, updater and launcher are
Bash-oriented and assume Linux-style paths.

Native Windows is not currently validated. Use WSL2 with Ubuntu/Debian for the
supported workflow. Manual native Windows usage is possible to explore because
the backend is Python and the frontend is browser-based, but there is no tested
PowerShell or `.bat` installer and command execution/path behavior is
experimental there.

### Recommended local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
python scripts/ensure_runtime_config.py
./venv/bin/pytest -q
./venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Verification commands

Backend:
```bash
make lint
./venv/bin/pytest -q
make script-check
```

Frontend:
```bash
cd frontend
npm run lint
npm run build
```

### Installed updates

Existing local installs should update through:

```bash
devsynapse update
```

or the direct alias created by the installer:

```bash
update-devsynapse
```

That flow preserves runtime configuration, backs up existing runtime state when
present, applies migrations and rebuilds the frontend bundle.

## Engineering Debt Register

The canonical planning source is [docs/development/roadmap.md](docs/development/roadmap.md).
Current engineering debt remains concentrated around:
- linting and formatting policy enforcement across backend and frontend;
- the WebSocket decision, if real-time transport becomes necessary;
- legacy artifact cleanup;
- clearer authorization policy objects if the product scope expands.

Legacy artifacts are now isolated under [legacy/README.md](legacy/README.md). They remain available for reference but are no longer part of the main runtime path.

## Documentation Policy

The project should document:
- what exists;
- what is partially implemented;
- what is planned.

It should not present roadmap items as completed capabilities. Engineering credibility is improved by precise scope control, not by inflated claims.

## Operational References

- Development workflow: [docs/development/workflow.md](docs/development/workflow.md)
- Runtime and CI notes: [docs/deployment/runtime.md](docs/deployment/runtime.md)
- User administration utility: [scripts/manage_users.py](scripts/manage_users.py)
