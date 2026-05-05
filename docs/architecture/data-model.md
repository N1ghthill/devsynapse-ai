# Persistence and Data Model

## Storage Strategy

DevSynapse AI currently uses SQLite for local persistence. Schema evolution is managed in-repo through explicit migrations.
Runtime connections are opened through `core.db.connect_db`, which applies a
shared timeout, `busy_timeout`, foreign key enforcement and WAL mode for
file-backed databases. Stores should not call `sqlite3.connect` directly.
Async store methods offload blocking SQLite calls through `core.async_utils.run_blocking`
instead of `asyncio.to_thread`.

Runtime database files are user state, not source files. By default they live under
`~/.local/share/devsynapse-ai/data`, with the primary SQLite path resolved from
`MEMORY_DB_PATH` in the runtime config. `DEVSYNAPSE_HOME` or
`DEVSYNAPSE_DATA_DIR` can relocate data files for a specific install.

Primary implementation files:
- [core/db.py](../../core/db.py)
- [core/migrations.py](../../core/migrations.py)
- [core/memory/agent_runs.py](../../core/memory/agent_runs.py)
- [core/memory/system.py](../../core/memory/system.py)
- [scripts/migrate.py](../../scripts/migrate.py)

## Main Persisted Concepts

### Conversations

Stores:
- user message
- assistant response
- stable `conversation_id` used as the visible chat/support ID
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
- project-aware attribution and telemetry
- restoring project scope when a persisted conversation continues

### Runtime settings

Stores:
- mutable application settings
- DeepSeek/OpenRouter/OpenCode credential presence and model parameters
- daily/monthly budget controls
- budget threshold percentages
- adaptive routing controls

These values supplement environment defaults and runtime config files.

### Project and preference context

Stores:
- known project name, path, type, priority and access metadata
- learned user preferences
- historical decisions and lessons

This context supports assistant prompt construction, command attribution and
project working-directory resolution. Project lists expose active registered
projects whose local directory still exists; stale registry rows can remain in
SQLite without deleting any project files.

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
SQLite state and can be inspected from the database or exported reporting
helpers.

### LLM model catalog

Stores:
- provider id (`deepseek`, `openrouter`, `opencode-go`, etc.)
- provider model id and display name
- context length when discovered
- input, output and cache-read cost per token when available
- raw provider pricing/capability metadata
- source URL and discovery timestamps
- enabled flag for routing eligibility

The catalog is populated by deterministic provider adapters rather than model
memory in the assistant. OpenRouter entries come from its Models API, OpenCode Go
entries come from the OpenAI-compatible models endpoint when available, and
direct DeepSeek entries are seeded from runtime pricing configuration.

### LLM request telemetry

Stores:
- user id and conversation id
- provider and model actually requested
- routing reason, task type and complexity
- success/error status
- token usage, cache hit/miss tokens, reasoning tokens and estimated cost
- first-token latency and total latency

This table is separate from conversation history so reporting can calculate
per-user/per-model cost, latency and error rate even when conversation rows are
summarized or exported separately.

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
are managed through the same local command policy used for other project writes.
Skills are loaded into the prompt when their metadata matches the current task,
and activation events are persisted for observability.

### Learning nudges

Stores:
- conversation and project scope
- nudge type, trigger reason and status
- structured details for created memory ids or skill slugs
- timestamp

The brain runs a deterministic review after complex turns and command
completion. Successful command outcomes can create or reinforce a procedural
memory and a global Markdown skill; complex non-command turns create lower
confidence insight memories.

### Project permissions

Stores:
- username
- project name
- permission type

This is retained as the project-scoped mutation policy table used by the command
bridge. TUI operator sessions use the trusted local-operator role, while the
bridge still keeps lower-trust role checks available for tests and future
restricted execution modes.

### Audit logs

Stores:
- actor
- target
- action
- structured details
- timestamp

### Agent runs

Stores:
- conversation id
- original goal
- project scope
- run status
- next action
- event timeline for command results, policy blocks, failures and final responses

This is the durable task state used by the coding agent to continue after missing
dependencies, blocked commands or resumed conversations without losing the
original objective.

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
- agent learning is advisory: it can influence model routing, but budget-critical
  economy mode still wins over learned Pro preferences
- adaptive LLM routing is advisory: it may choose a cheaper discovered model for
  simple or budget-constrained work, but only when the provider is configured and
  the catalog contains usable pricing
- skill activation is advisory prompt context; shell/file effects still go through
  the existing command execution and authorization flow
- agent runs are advisory execution state; command authorization and project
  scope enforcement remain in the command bridge

## Current Tradeoff

SQLite is a good fit for:
- local development
- contributor onboarding
- single-node operational usage

It is not yet positioned as a full distributed or multi-tenant persistence strategy.
