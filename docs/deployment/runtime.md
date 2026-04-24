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
