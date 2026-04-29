# Persistence and Data Model

## Storage Strategy

DevSynapse AI currently uses SQLite for local persistence. Schema evolution is managed in-repo through explicit migrations.

Runtime database files are user state, not source files. By default they live under
`~/.local/share/devsynapse-ai/data`, with paths resolved from `MEMORY_DB_PATH` and
`MONITORING_DB_PATH` in the runtime config. `DEVSYNAPSE_HOME` or
`DEVSYNAPSE_DATA_DIR` can relocate them for a specific install.

Primary implementation files:
- [core/db.py](../../core/db.py)
- [core/migrations.py](../../core/migrations.py)
- [core/memory/system.py](../../core/memory/system.py)
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
- restoring project scope in the chat UI when a persisted conversation is opened

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
Administrators can register additional existing local project directories at runtime; these rows are persisted and are loaded into command attribution and project working-directory resolution.
User-facing project lists expose only active registered projects whose local
directory still exists. Administrative project management lists both active and
stale registry rows, includes the local path and `path_exists` status, and can
remove a registry entry without deleting files from disk.

### Agent learning

Stores:
- semantic task signatures and task type
- preferred model for similar future tasks
- confidence, success and failure counts
- recent evidence from feedback and command outcomes
- route decision telemetry including selected model, fallback, budget mode, cache
  hit rate and estimated cost

This lets the agent use prior local outcomes when choosing Flash or Pro, instead
of treating every request as a stateless prompt. Learned patterns are local
SQLite state and are surfaced in monitoring stats.

### Procedural memories

Stores:
- project name, memory type and content
- source, tags and structured metadata
- `confidence_score` as the base trust value
- `memory_decay_score` as the daily decay coefficient
- evidence and access counts
- computed effective confidence at read time

Effective confidence decays with age, then receives bounded boosts from evidence
and access counts. This keeps stale one-off memories from dominating prompts
while allowing repeated successful evidence to stay visible. Relevant memories
are injected into the assistant prompt by project scope and lexical task match.

### Skills

Stores:
- skill name, slug, category and description
- scope (`global` or `project`) and optional project name
- `SKILL.md` path, content hash and activation metadata
- usage count and last-used timestamp

Global skills are stored under the local DevSynapse data directory. Explicit
project skills live under `.devsynapse/skills` inside a registered project and
are admin-managed because they write to the project tree. Skills are loaded into
the prompt when their metadata matches the current task, and activation events
are persisted for observability.

### Learning nudges

Stores:
- conversation and project scope
- nudge type, trigger reason and status
- structured details for created memory ids or skill slugs
- timestamp

The backend runs a deterministic review after complex turns and command
completion. Successful command outcomes can create or reinforce a procedural
memory and a global Markdown skill; complex non-command turns create lower
confidence insight memories.

### Project permissions

Stores:
- username
- project name
- permission type

This is the basis for project-scoped mutation authorization for non-admin users.
Admin users are trusted local operators and do not depend on rows in this table.
Non-admin path-based mutating commands must stay inside the resolved registered project.

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
- streaming chat should return the resolved persisted project name in the terminal
  `done` event when attribution is available
- agent learning is advisory: it can influence model routing, but budget-critical
  economy mode still wins over learned Pro preferences
- skill activation is advisory prompt context; shell/file effects still go through
  the existing command execution and authorization flow

## Current Tradeoff

SQLite is a good fit for:
- local development
- contributor onboarding
- single-node operational usage

It is not yet positioned as a full distributed or multi-tenant persistence strategy.
