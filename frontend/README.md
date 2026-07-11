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
../scripts/desktop-smoke.sh
```

## Backend Sidecar

The desktop shell starts `backend-entry.py` in development and checks
authenticated `/health` and `/version` endpoints on a private loopback port.
The sidecar also exposes typed conversation and read-only operation contracts.
It does not expose shell execution or raw Git/GitHub responses.

For packaged builds, create the sidecar binary first:

```bash
npm run backend:build
```
