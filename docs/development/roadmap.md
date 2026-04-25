# Development Roadmap

This roadmap is the planning source for near-term DevSynapse AI development.
It distinguishes completed baseline capabilities from active priorities and later work.
Do not present planned items as shipped behavior in user-facing documentation.

## Current Baseline

The current documented baseline is `v0.3.3`, validated on `2026-04-25`.
It includes:

- local-first FastAPI, React/Vite and SQLite architecture;
- migration-managed persistence;
- JWT authentication with persisted users;
- project-scoped mutation authorization for non-admin users;
- administrative audit logging for permission changes;
- conversation persistence, rehydration, rename and delete flows;
- LLM token and cost telemetry;
- dashboard usage reporting and CSV export;
- configurable daily/monthly LLM budget thresholds with alert emission (enabled by default);
- contributor documentation, security policy and release notes;
- DeepSeek-first API-key based LLM integration;
- portable configuration via environment variables (no hardcoded user paths);
- SSE streaming chat with real-time token delivery;
- project selector in chat UI;
- working directory resolution per project for bash/grep commands;
- keyboard shortcuts for chat input (Enter, Ctrl+Enter, Shift+Enter);
- portable CI and setup validation for shell scripts, frontend linting and installer/uninstaller smoke tests;
- Docker delivery with a FastAPI runtime image that serves the production frontend bundle;
- admin project registration for existing local project directories.

## Current Priorities

These items should be treated as the next practical development focus:

- strengthen explicit project attribution across chat, execution and reporting flows; see [project-attribution.md](project-attribution.md)
- sharpen the DeepSeek-first product path: budget-aware usage, clearer setup, and no local-model/provider-neutral positioning;
- deepen route-level and integration coverage for auth, execution, monitoring and settings;
- improve dashboard clarity for budget, usage, project cost and alert state;
- tighten linting and formatting policy enforcement across backend and frontend;
- improve contributor ergonomics for issues, pull requests and release preparation.

## Next Design Decisions

These need design clarity before implementation:

- whether real-time transport is needed before adding WebSocket complexity;
- how project allowlists should evolve into clearer authorization policy objects;
- how much production hardening belongs in this repository versus deployment-specific guidance;
- which legacy artifacts should remain as historical references and which should be removed.

## Later Work

These are valuable but not immediate baseline requirements:

- stronger secrets rotation and incident-response procedures;
- more formal user administration workflows;
- richer integration and end-to-end frontend coverage;
- production deployment validation for Docker, reverse proxy and persistent volumes;
- a longer-term persistence strategy if multi-user or multi-node use becomes a product goal.

## Explicitly Deferred

The current project should not claim these as complete:

- kernel-level sandbox isolation;
- enterprise RBAC;
- distributed or multi-tenant database architecture;
- production-complete security hardening;
- local quantized model execution;
- provider-neutral model routing as a primary product direction.

## Maintenance Rule

When a roadmap item ships, update the relevant runtime docs, `CHANGELOG.md`, release notes and this file in the same change. Remove or reclassify stale items rather than leaving completed work listed as future scope.
