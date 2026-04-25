# Persistence and Data Model

## Storage Strategy

DevSynapse AI currently uses SQLite for local persistence. Schema evolution is managed in-repo through explicit migrations.

Primary implementation files:
- [core/db.py](../../core/db.py)
- [core/migrations.py](../../core/migrations.py)
- [core/memory.py](../../core/memory.py)
- [scripts/migrate.py](../../scripts/migrate.py)

## Main Persisted Concepts

### Conversations

Stores:
- user message
- assistant response
- proposed command
- execution result and status
- explicit conversation title
- explicit or inferred project attribution
- LLM usage telemetry
- feedback metadata

This table is central to:
- chat history rehydration
- execution status persistence
- token and cost reporting
- conversation lists and export
- project-aware authorization, telemetry and dashboard reporting

### Users

Stores:
- username
- password hash
- role
- active state
- login timestamps

### Runtime settings

Stores:
- mutable application settings
- DeepSeek model and generation parameters
- daily/monthly budget controls
- budget threshold percentages

These values back `/settings` and supplement environment defaults.

### Project and preference context

Stores:
- known project name, path, type, priority and access metadata
- learned user preferences
- historical decisions and lessons

This context supports assistant prompt construction and project-aware reporting.

### Project permissions

Stores:
- username
- project name
- permission type

This is the basis for project-scoped mutation authorization for non-admin users.

### Admin audit logs

Stores:
- actor
- target
- action
- structured details
- timestamp

### Monitoring schema

Stores:
- command execution telemetry
- API usage telemetry
- generic system metrics
- alerts

## Migration Discipline

Use:

```bash
make migration-status
make migrate
```

Contributors should add a new migration when:
- a column is added or removed
- a table is introduced
- persisted telemetry shape changes
- a feature requires historical data persistence

## Data Integrity Notes

- newer conversation rows can carry richer telemetry than older rows
- historical rows are intentionally tolerated with partial fields
- project attribution now prefers explicit persisted project names over text-only inference
- explicit chat project context should be persisted as `conversation_project_name`

## Current Tradeoff

SQLite is a good fit for:
- local development
- contributor onboarding
- single-node operational usage

It is not yet positioned as a full distributed or multi-tenant persistence strategy.
