# API Overview

## Canonical Contract Source

The live contract source is the FastAPI OpenAPI spec at:
- `http://127.0.0.1:8000/docs`

Static schema definitions live in [api/models.py](../../api/models.py).

## Route Groups

### Auth

- `POST /auth/login`
- `GET /auth/verify`

Purpose:
- obtain and validate JWT credentials

### Chat

- `POST /chat`
- `GET /chat/history`
- `GET /conversations`
- `GET /conversations/{conversation_id}`
- `PUT /conversations/{conversation_id}`
- `DELETE /conversations/{conversation_id}`
- `GET /conversations/export/usage.csv`
- `POST /execute`
- `POST /feedback`

Purpose:
- assistant interaction
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

Purpose:
- inspect and update runtime-adjustable settings

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
- `ChatResponse` carries `llm_usage` when provider usage metadata is available
- `/execute` returns structured execution status, reason code and project context
- `/monitoring/stats` includes `llm_usage` aggregates and project-level breakdown

## Authentication Behavior

- protected routes require a valid bearer token
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
