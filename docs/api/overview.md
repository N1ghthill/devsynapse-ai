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
- list known project metadata used for project context

### Admin

- `GET /admin/users`
- `PUT /admin/users/{username}/permissions`
- `GET /admin/audit-logs`

Purpose:
- inspect users
- manage project-scoped mutation permissions
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

## Authentication Behavior

- routes using `require_user` or `require_admin` require a valid bearer token
- admin routes require an admin role
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
