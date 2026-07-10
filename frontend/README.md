# DevSynapse Desktop

This is the target desktop workspace for DevSynapse AI.

The current milestone is a minimal Tauri 2 + React/TypeScript shell. It
intentionally excludes the historical login, admin, dashboard, knowledge and
generic command execution screens.

## Commands

```bash
npm install
npm run lint
npm run typecheck
npm run build
npm run tauri:dev
```

The backend sidecar lifecycle is planned for the next increment. Until then,
the desktop shell exposes only local app health/version commands.

## Backend Sidecar

The desktop shell starts `backend-entry.py` in development and checks
authenticated `/health` and `/version` endpoints on a private loopback port.
The endpoint surface is lifecycle-only; it does not expose shell execution or
Git/GitHub operations.

For packaged builds, create the sidecar binary first:

```bash
npm run backend:build
```
