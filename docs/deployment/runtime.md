# Runtime and Delivery Notes

## CI Baseline

The repository now includes a GitHub Actions workflow at [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

Current checks:
- Python dependency installation
- Ruff lint pass
- backend test suite
- frontend dependency installation
- frontend production build

## Authorization Boundary

`/execute` now requires authentication and applies role-aware authorization inside the command bridge:
- read-only inspection commands are available to regular users;
- mutating actions such as `edit`, `write` and sensitive bash commands require explicit permission context.
- regular users may receive mutation permission for explicit projects through per-user settings, but only when project context can be resolved from the request or command path.
- administrative changes to per-user project permissions are exposed through `/admin/users/{username}/permissions` and tracked in `/admin/audit-logs`.

## LLM Budget Controls

Runtime-adjustable budget settings are exposed through `/settings` and persisted in SQLite-backed app settings.
The runtime is DeepSeek-first and API-key based; local quantized model execution is not part of the supported product direction.

Current controls:
- `LLM_DAILY_BUDGET_USD`
- `LLM_MONTHLY_BUDGET_USD`
- `LLM_BUDGET_WARNING_THRESHOLD_PCT`
- `LLM_BUDGET_CRITICAL_THRESHOLD_PCT`

Operational behavior:
- `0` disables the corresponding budget window
- daily budget uses the last `24h`
- monthly budget uses the current calendar month
- `/monitoring/stats` exposes the current budget snapshot for UI/reporting
- active alerts are created when warning or critical thresholds are crossed

## Database Schema Management

SQLite schema changes are versioned through the in-repo migration layer.

Operational commands:

```bash
make migration-status
make migrate
```

Implementation references:
- [core/db.py](../../core/db.py)
- [core/migrations.py](../../core/migrations.py)
- [scripts/migrate.py](../../scripts/migrate.py)

This is the minimum engineering gate for keeping backend and frontend contracts aligned.

## Docker

The existing [Dockerfile](../../Dockerfile) still provides a useful container baseline, but it should be treated as an evolving asset rather than a final production artifact.

Before production use, validate:
- runtime user permissions
- asset serving strategy
- environment variable injection
- database volume persistence
- reverse proxy expectations

## Nginx

[nginx.conf](../../nginx.conf) now reflects the current frontend entrypoint and no longer advertises unsupported WebSocket paths.

## Delivery Standard

A change should be considered integration-ready only when:
- backend tests pass;
- frontend build passes;
- documentation is updated when contracts or operational flows change.
