# Screenshots and Evidence

This directory contains curated screenshots and a derived demo GIF for public
documentation, release notes and contributor context. They are based on product
evidence, not fabricated mockups. Use them to show what the local FastAPI +
React/Vite app currently exposes.

## Current Set

- [2026-04-24-login-screen.png](2026-04-24-login-screen.png)
  Login screen for the operator UI.
- [2026-04-24-chat-command-execution.png](2026-04-24-chat-command-execution.png)
  Chat workflow showing a successful `bash` execution and a blocked command with explicit status.
- [2026-04-24-dashboard-llm-usage.png](2026-04-24-dashboard-llm-usage.png)
  Dashboard view with command stats, LLM usage and project cost reporting.
- [2026-04-24-settings-project-access.png](2026-04-24-settings-project-access.png)
  Settings view with DeepSeek API key state, model configuration, budget controls and project mutation scope.
- [2026-04-24-admin-project-permissions.png](2026-04-24-admin-project-permissions.png)
  Admin panel showing project mutation permissions and audit history.
- [devsynapse-demo-flow.gif](devsynapse-demo-flow.gif)
  Short top-of-README product loop assembled from the current screenshots:
  project context, command review, execution interpretation, usage telemetry and
  DeepSeek budget/project controls.

## Use-Case Mapping

- **Budget-conscious developer:** settings and dashboard screenshots show DeepSeek configuration, token/cost reporting and budget thresholds.
- **Freelancer with multiple projects:** dashboard, settings and admin screenshots show project attribution, project mutation scope and permission management.
- **Local coding operator:** chat screenshot shows command proposal/execution state instead of hidden shell access.

The narrative version is maintained in [../product/showcase.md](../product/showcase.md).

## Regenerating Screenshots

The still screenshots can be regenerated from a running local environment with:

```bash
cd frontend
npm install
npm run capture:docs-screenshots
```

Requirements:
- frontend available on `http://127.0.0.1:5173`
- backend available on `http://127.0.0.1:8000`
- default local user seeded: `admin`
- credentials are read from `DEFAULT_USER_*` and `DEFAULT_ADMIN_*` in the runtime config when present

The automation script is stored in [../../frontend/scripts/capture-doc-screenshots.mjs](../../frontend/scripts/capture-doc-screenshots.mjs).

The demo GIF is a derived README asset assembled from the still screenshots.
Replace or regenerate it whenever the documented product flow changes.

## Guidelines

- prefer screenshots that demonstrate current behavior rather than mockups
- avoid exposing secrets, tokens or unrelated personal data
- keep file names descriptive and date-stamped
- refresh this index when screenshots are added, replaced or removed
- refresh screenshots when UI labels or supported provider/model behavior changes
