# Project Attribution Plan

Project attribution connects chat, command execution, authorization, telemetry and dashboard reporting.
The goal is to prefer explicit project context and fall back to inference only when that inference is reliable.

## Current Sources

Project context can come from:
- explicit request fields such as `project_name`;
- command paths resolved against known projects;
- persisted `conversation_project_name`;
- administrator-registered project paths;
- legacy text inference from messages and commands.

## Contract Rules

- Mutating execution for non-admin users must require an explicit or resolvable project.
- Admin users have global mutation scope across registered projects and do not use per-user allowlists.
- Mutating file and path-based bash commands must only target paths inside the resolved registered project.
- Admin-registered project paths must be available to command attribution and working-directory resolution.
- Regular `/projects` responses must not expose local project paths; `/admin/projects` is the path-bearing management surface.
- `/execute` responses must include `project_name` when the bridge resolves one.
- `POST /chat` may receive `project_name` and must persist it with the conversation row.
- Later chat turns should reuse the persisted conversation project when no new project is provided.
- Chat history and conversation detail responses must return persisted `project_name` when available.
- Conversation persistence should store explicit project names when available.
- Reporting should prefer persisted project names over text-only inference.
- The frontend should display backend-provided project names, not derive them independently.

## Current Gaps

- Some chat flows still rely on inferred project context from message text.
- Older conversation rows may not have `conversation_project_name`.
- Dashboard reporting still needs clearer visibility into attributed, inferred and unattributed usage.

## Completed

- **Frontend project selector** (v0.3.0): the chat UI now includes a dropdown populated from `/projects` that sends the selected project as `project_name` in chat and command-execution requests.

## Next Implementation Steps

1. Distinguish explicit, inferred and unattributed project usage in monitoring data.
2. Update dashboard labels so project attribution quality is visible to operators.
3. Consider backfilling project attribution for historical rows when inference is reliable.

## Documentation Rule

Any change to project attribution must update API docs, data model docs, frontend types and tests in the same change.
