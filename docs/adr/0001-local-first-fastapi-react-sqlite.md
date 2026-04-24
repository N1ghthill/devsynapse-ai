# ADR 0001: Local-First FastAPI + React + SQLite Architecture

## Status

Accepted

## Context

DevSynapse AI needed a practical architecture that:
- could be developed and verified quickly on a local machine
- kept backend contracts explicit
- supported a browser-based operator UI
- persisted runtime state without immediate infrastructure overhead

## Decision

Use:
- FastAPI for the backend HTTP surface
- React/Vite for the frontend
- SQLite for persistence
- migration-managed schemas in-repo

## Consequences

Positive:
- low setup friction
- easy contributor onboarding
- explicit API contracts
- no immediate dependency on external databases

Tradeoffs:
- SQLite is not a long-term multi-tenant production answer
- local-first runtime assumptions remain visible in the codebase
- command execution safety still depends on application-layer controls
