# API Overview

## Canonical Contract Source

The live contract source is the FastAPI OpenAPI spec at:
- `http://127.0.0.1:8000/docs`

Static schema definitions live in [api/models.py](../../api/models.py).

## Route Groups

### API info

- `GET /api`

Purpose:
- expose service name, version, status and core endpoint links

### Auth

- `POST /auth/login`
- `GET /auth/verify`

Purpose:
- obtain and validate JWT credentials

### Bootstrap

- `GET /bootstrap/status`
- `POST /bootstrap/complete`

Purpose:
- report whether first-run setup is still required
- configure the initial admin password, DeepSeek API key and repository workspace
- allow authenticated admins to complete missing runtime setup after an update

### Chat

- `POST /chat`
- `POST /chat/stream`
- `GET /chat/history`
- `GET /conversations`
- `GET /conversations/{conversation_id}`
- `PUT /conversations/{conversation_id}`
- `DELETE /conversations/{conversation_id}`
- `GET /conversations/export/usage.csv`
- `POST /execute`
- `POST /feedback`

Purpose:
- assistant interaction (blocking and streaming)
- conversation persistence
- command execution
- usage export

### Monitoring

- `GET /health`
- `GET /monitoring/health`
- `GET /monitoring/stats`
- `GET /monitoring/alerts`
- `POST /monitoring/alerts/{alert_id}/resolve`

Purpose:
- service health
- API and command telemetry
- LLM usage and cost reporting
- alert lifecycle

### Knowledge

- `GET /knowledge/stats`
- `GET /memories`
- `POST /memories`
- `POST /memories/{memory_id}/feedback`
- `GET /skills`
- `POST /skills`
- `GET /skills/{skill_name}`
- `POST /skills/{skill_name}/activate`
- `PATCH /skills/{skill_name}`
- `DELETE /skills/{skill_name}`

Purpose:
- store project-scoped procedural memories with confidence and decay metadata
- list, create and activate Markdown-backed skills
- expose learning nudge, memory and skill counts for the dashboard

### Settings

- `GET /settings`
- `PUT /settings`
- `GET /projects`

Purpose:
- inspect runtime-adjustable settings
- update global runtime-adjustable settings as an admin
- configure the DeepSeek API key, default/Flash/Pro models, routing mode, cache threshold and generation limits
- list project metadata for user-facing project selection without exposing local paths

### Admin

- `GET /admin/users`
- `PUT /admin/users/{username}/permissions`
- `GET /admin/projects`
- `POST /admin/projects`
- `GET /admin/audit-logs`

Purpose:
- inspect users
- manage project-scoped mutation permissions
- register known projects for project context and command working-directory resolution
- review administrative changes

## Contract Notes

- the frontend should not invent payload shapes
- `ChatRequest.project_name` can carry explicit project context for a conversation turn;
  once a conversation has a persisted project, later chat and execution requests for
  that conversation must use the same project or omit the field
- `ChatResponse.project_name` returns explicit or persisted conversation project context when available
- `ChatResponse` carries `llm_usage` when DeepSeek usage metadata is available
- `/chat/stream` returns SSE events: `text` chunks, `command` when extracted, `command_status` and `command_result` when `ChatRequest.execute_command` enables automatic execution, and `done` with usage metadata and resolved `project_name` when available
- `/chat/stream` does not expose provider reasoning content to clients; internal reasoning may still be used by the model provider but is not part of the UI contract
- when `ChatRequest.execute_command` is enabled and an action-oriented request gets either an empty model response or intent text without a tool call, the backend retries that turn with a strict "emit one tool call or final answer" instruction before ending the stream
- admin automatic streaming runs supported OpenCode commands without project allowlist confirmation and can continue after ordinary command execution failures by feeding the failure output back to the model; selected conversation project scope, validation, blacklist, plugin and authorization blocks still end the run
- `/execute` returns structured execution status, reason code and project context
- `/execute` normalizes common LLM placeholder paths such as `/home/user/projects`, `~/projects` and `/workspace` to the configured local repository/workspace roots before validation and execution; if a mutating command points outside the selected conversation project, execution is blocked with `project_scope_mismatch`, while read-only reference commands can inspect other allowed or registered repositories
- `/chat/history`, `/conversations` and `/conversations/{conversation_id}` include persisted `project_name` when available
- `/monitoring/stats` includes `llm_usage` aggregates, cache hit-rate telemetry, project-level breakdown, agent learning stats and budget status snapshots
- `/monitoring/stats` also includes `llm_usage.knowledge` with memory, skill and nudge aggregates
- `/memories` returns both base `confidence_score` and computed `effective_confidence`; the effective score applies `memory_decay_score`, evidence and access signals
- skill writes create `SKILL.md` files under the local DevSynapse data directory by default; explicit project skills use `.devsynapse/skills` inside the registered project
- skill write/delete routes require an admin role, while listing and activation require an authenticated user
- `llm_model_routing_enabled` lets the backend route simple and medium work to Flash while keeping complex work on Pro
- `llm_auto_economy_enabled` forces Flash routing when budget status is critical
- `/feedback` updates conversation feedback and can create agent-learning signals used by future routing decisions
- `/projects` returns registered project `name`, `type`, `priority`, `last_accessed` and `access_count`
- `/admin/projects` returns registered projects with local `path` for administrative management
- `POST /admin/projects` registers an existing local project directory; with
  `create_directory=true`, admins can create the directory first, defaulting to
  `DEV_REPOS_ROOT/<project-slug>` when `path` is omitted
- `POST /admin/projects` rejects duplicate project names; updates should be explicit future behavior

## Authentication Behavior

- routes using `require_user` or `require_admin` require a valid bearer token
- chat, conversation, feedback, settings reads, project, monitoring stats/alerts, execution and usage export routes require an authenticated user
- `/bootstrap/status` is public so the desktop app can decide whether to show onboarding
- `/bootstrap/complete` is public only while the seeded admin still requires first-run password setup; after that it requires an authenticated admin
- `/health` and `/monitoring/health` remain public readiness endpoints
- `PUT /settings` requires an admin role because it changes global runtime behavior
- project memory writes require admin role for global memories or project mutation permission for project-scoped memories
- admin routes require an admin role
- admin users are trusted local operators: they can execute supported OpenCode tools without per-user project allowlists, and admin `bash` supports shell syntax
- non-admin users keep project-scoped mutation permissions and conservative chat auto-execution; the frontend "Aprovar tudo" mode removes repeated confirmation clicks only for commands the backend still authorizes
- frontend currently redirects to `/login` on `401`

## Contributor Rule

If you change:
- field names
- response shape
- route availability
- auth requirements

then update:
- [api/models.py](../../api/models.py)
- relevant route docs
- frontend contract files under `frontend/src/api/` and `frontend/src/types.ts`
