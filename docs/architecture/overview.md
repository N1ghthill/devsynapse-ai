# Architecture Overview

## Purpose

DevSynapse AI is structured as a local-first assistant platform with three major concerns:
- user and project context
- LLM orchestration and response handling
- constrained command execution with observability

## High-Level Flow

```text
React/Vite frontend
        |
        v
FastAPI routes
        |
        v
Core services
  - brain
  - auth
  - memory
  - opencode bridge
  - monitoring
  - plugin system
        |
        v
SQLite persistence + local runtime state
```

## Backend Layers

### API layer

Main files:
- [api/app.py](../../api/app.py)
- [api/dependencies.py](../../api/dependencies.py)
- [api/models.py](../../api/models.py)
- [api/routes/auth.py](../../api/routes/auth.py)
- [api/routes/chat.py](../../api/routes/chat.py)
- [api/routes/monitoring.py](../../api/routes/monitoring.py)
- [api/routes/settings.py](../../api/routes/settings.py)
- [api/routes/admin.py](../../api/routes/admin.py)

Responsibilities:
- expose HTTP endpoints
- validate request/response payloads
- compose services from shared dependencies
- keep transport concerns separate from core logic

### Core services

Main files:
- [core/brain.py](../../core/brain.py)
- [core/auth.py](../../core/auth.py)
- [core/memory.py](../../core/memory.py)
- [core/opencode_bridge.py](../../core/opencode_bridge.py)
- [core/monitoring.py](../../core/monitoring.py)
- [core/plugin_system.py](../../core/plugin_system.py)

Responsibilities:
- `brain.py`: prompt construction, provider calls, command extraction, repair and telemetry
- `auth.py`: password hashing and JWT validation
- `memory.py`: persistence for conversations, users, permissions, telemetry and settings
- `opencode_bridge.py`: validation, authorization and execution of constrained commands
- `monitoring.py`: command/API metrics and alerts
- `plugin_system.py`: lifecycle extension points

## Frontend Responsibilities

Main files:
- [frontend/src/App.tsx](../../frontend/src/App.tsx)
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts)
- [frontend/src/types.ts](../../frontend/src/types.ts)
- [frontend/src/pages/Chat.tsx](../../frontend/src/pages/Chat.tsx)
- [frontend/src/pages/Dashboard.tsx](../../frontend/src/pages/Dashboard.tsx)
- [frontend/src/pages/Settings.tsx](../../frontend/src/pages/Settings.tsx)
- [frontend/src/pages/Admin.tsx](../../frontend/src/pages/Admin.tsx)

Responsibilities:
- authenticate the user
- render chat and execution flows
- show monitoring and cost telemetry
- keep frontend contracts aligned with backend payloads

## Runtime Principles

- route contracts are authoritative in the backend
- schema evolution is explicit through migrations
- mutating command execution is project-aware
- telemetry is persisted, not just derived on the fly
- documentation is part of the runtime contract surface

## Current Maturity

The architecture is coherent and contributor-friendly, but still early-stage in production maturity. The correct description is:
- strong local engineering baseline
- open source contributor-ready
- not yet a full enterprise-hardened deployment platform
