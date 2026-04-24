# Screenshots and Evidence

This directory contains curated screenshots for public documentation, release notes and contributor context.

## Current Set

- [2026-04-24-login-screen.png](2026-04-24-login-screen.png)
  Login screen for the operator UI.
- [2026-04-24-chat-command-execution.png](2026-04-24-chat-command-execution.png)
  Chat workflow showing a successful `bash` execution and a blocked command with explicit status.
- [2026-04-24-dashboard-llm-usage.png](2026-04-24-dashboard-llm-usage.png)
  Dashboard view with command stats, LLM usage and project cost reporting.
- [2026-04-24-settings-project-access.png](2026-04-24-settings-project-access.png)
  Settings view with model configuration and project mutation scope.
- [2026-04-24-admin-project-permissions.png](2026-04-24-admin-project-permissions.png)
  Admin panel showing project mutation permissions and audit history.

## Regenerating Screenshots

The current set can be regenerated from a running local environment with:

```bash
cd frontend
npm install
npm run capture:docs-screenshots
```

Requirements:
- frontend available on `http://127.0.0.1:5173`
- backend available on `http://127.0.0.1:8000`
- default local users seeded: `irving` and `admin`

The automation script is stored in [../../frontend/scripts/capture-doc-screenshots.mjs](../../frontend/scripts/capture-doc-screenshots.mjs).

## Guidelines

- prefer screenshots that demonstrate current behavior rather than mockups
- avoid exposing secrets, tokens or unrelated personal data
- keep file names descriptive and date-stamped
- refresh this index when screenshots are added, replaced or removed
