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
- command execution refreshes the bridge project lookup from the persisted registry before
  resolving project scope
- projects inferred under the configured repositories root may be registered after a
  successful command so generated projects remain discoverable in later conversations
- automatic execution replays recoverable command failures or policy blocks to the model so
  it can continue with an allowed project-scoped action or explain the exact permission needed
- agent task runs persist the original goal, command events and next action so
  blocked or failed commands remain recoverable context in later turns

## Consequences

Positive:
- tighter control over write-capable actions
- clearer operational model for collaboration
- better auditability

Tradeoffs:
- project attribution must be reliable
- some generic conversations cannot be attributed cleanly
- dashboard project cost reporting is only as strong as the available project context
- blocked commands may consume an extra LLM turn in auto-execution mode to produce a useful
  fallback instead of ending on the raw policy error
- the task-run log is advisory context; authorization decisions still happen at
  execution time in the command bridge
