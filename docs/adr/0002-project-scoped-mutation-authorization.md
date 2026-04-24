# ADR 0002: Project-Scoped Mutation Authorization

## Status

Accepted

## Context

The assistant can propose and execute commands that read and mutate local files. A flat allow/deny model was not sufficient because collaborators needed write access for some projects without opening write access globally.

## Decision

Adopt project-scoped mutation authorization:
- read-only flows remain broadly available to regular users
- mutating actions require explicit project context
- non-admin mutation access is granted per user and per project
- administrative changes are auditable

## Consequences

Positive:
- tighter control over write-capable actions
- clearer operational model for collaboration
- better auditability

Tradeoffs:
- project attribution must be reliable
- some generic conversations cannot be attributed cleanly
- dashboard project cost reporting is only as strong as the available project context
