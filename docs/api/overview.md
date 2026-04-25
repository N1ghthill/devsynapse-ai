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

### Settings

- `GET /settings`
- `PUT /settings`
- `GET /projects`

Purpose:
- inspect and update runtime-adjustable settings
- configure the DeepSeek API key, DeepSeek model and generation limits
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
- `ChatRequest.project_name` can carry explicit project context for a conversation turn
- `ChatResponse.project_name` returns explicit or persisted conversation project context when available
- `ChatResponse` carries `llm_usage` when DeepSeek usage metadata is available
- `/chat/stream` returns SSE events: `text` chunks, `command` when extracted, `done` with usage metadata
- `/execute` returns structured execution status, reason code and project context
- `/chat/history` and `/conversations/{conversation_id}` include persisted `project_name` when available
- `/monitoring/stats` includes `llm_usage` aggregates, project-level breakdown and budget status snapshots
- `/projects` returns registered project `name`, `type`, `priority`, `last_accessed` and `access_count`
- `/admin/projects` returns registered projects with local `path` for administrative management
- `POST /admin/projects` registers an existing local project directory; it does not scaffold files
- `POST /admin/projects` rejects duplicate project names; updates should be explicit future behavior

## Authentication Behavior

- routes using `require_user` or `require_admin` require a valid bearer token
- chat, conversation, feedback, settings, project, monitoring stats/alerts, execution and usage export routes require an authenticated user
- `/health` and `/monitoring/health` remain public readiness endpoints
- admin routes require an admin role
- admin users have global mutation scope across registered projects and do not use per-user project allowlists
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
