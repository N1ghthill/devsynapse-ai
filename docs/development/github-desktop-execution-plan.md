# GitHub Desktop Execution Plan

## Purpose

This plan turns the DevSynapse product direction into an implementation track
for a packaged desktop GitHub assistant.

The target product is a Tauri 2 + React/TypeScript desktop application with a
bundled Python backend. Users converse with the assistant, inspect evidence,
approve previews and execute typed Git/GitHub operations. The Textual TUI,
slash commands and generic command bridge remain transitional developer
surfaces only.

## Guiding Constraints

- The desktop application is the target end-user surface.
- GitHub and GitHub Actions are primary domain boundaries, not plugins.
- The model may propose actions, but policy and operation authorization are
  deterministic backend responsibilities.
- Frontend code never receives provider tokens, GitHub tokens, secret values or
  raw GitHub API payloads.
- New product workflows use registered typed operations, not shell text.
- Every consequential local or remote mutation requires a current immutable
  preview and explicit confirmation.
- Destructive actions remain unavailable by default.

## Current Baseline

Current code:

- Python conversation core, memory, routing and provider transport.
- Tauri 2 + React/TypeScript desktop shell with Conversation, Projects,
  Activity and Settings.
- Python sidecar lifecycle with authenticated private loopback IPC.
- Typed conversation contracts and initial operation registry.
- Native project-folder selection and local project registration.
- Read-only Git evidence operations and `commit.preview` prepare operation.
- GitHub OAuth Device Flow operations using platform keyring storage.
- GitHub repository listing/search and local project to GitHub repository
  association through typed desktop operations.
- Transitional Textual TUI and slash command catalog for development
  migration.

Historical code at commit `5019c19`:

- Tauri 2 desktop shell.
- React/TypeScript/Vite frontend.
- Icons and packaging configuration.
- Python sidecar build concept.
- Legacy screens that must not be restored wholesale.

Missing target capabilities:

- installable clean-machine desktop packages;
- normalized GitHub Actions domain models;
- visual approval binding for local and remote mutations;
- persisted operation audit records;
- accessibility and packaging coverage beyond the current smoke/build checks.

## Delivery Strategy

The migration proceeds in small, reviewable increments. Each increment keeps
the repository usable and avoids expanding the legacy TUI as a product surface.

### Increment 1: Minimal Desktop Workspace

Goal: restore the desktop build foundation without restoring legacy product
screens.

Deliverables:

- `frontend/` React/TypeScript/Vite workspace.
- `frontend/src-tauri/` Tauri 2 workspace.
- DevSynapse icons and application identity.
- Minimal first screen with four target destinations:
  Conversation, Projects, Activity and Settings.
- Contributor commands for frontend lint, typecheck and build.
- No login/admin/provider dashboard/knowledge management screens.
- No generic command execution UI.
- No sidecar lifecycle yet.

Acceptance checks:

- `npm run build` succeeds inside `frontend/` when dependencies are installed.
- `cargo check` succeeds inside `frontend/src-tauri/`.
- Desktop navigation is limited to the four target areas.
- The UI labels GitHub connection and typed operations as upcoming when they
  are not implemented yet.

### Increment 2: Backend Sidecar Lifecycle

Goal: launch and supervise the bundled Python backend from the desktop app.

Deliverables:

- Backend entrypoint for sidecar mode.
- PyInstaller build script reviewed for current Python package layout.
- Tauri sidecar startup, shutdown, health and restart commands.
- User-scoped runtime directories.
- Redacted logs.
- Visual backend health state.

Acceptance checks:

- App starts backend on launch.
- Backend exits when app exits.
- Startup failure appears in the UI with a recovery action.
- No generic command endpoint is exposed to the frontend.

Current implementation notes:

- Development runs use `backend-entry.py` through the local Python runtime.
- The sidecar exposes only authenticated `/health` and `/version` lifecycle
  endpoints.
- `scripts/build-backend.sh` prepares a PyInstaller binary at the Tauri
  sidecar path for packaged builds.
- The default Tauri config does not require the generated binary for
  `cargo check`; packaging should run the backend build first.

### Increment 3: Typed IPC and Streaming Conversation

Goal: replace ad hoc frontend/backend coupling with typed desktop contracts.

Deliverables:

- Request and response schemas for:
  `app.health`, `app.version`, `conversation.start`,
  `conversation.send`, `conversation.cancel`, `project.list`,
  `project.register`.
- Streaming event model:
  `response.started`, `response.delta`, `response.completed`,
  `response.failed`, `operation.started`, `operation.progress`,
  `operation.completed`, `operation.failed`.
- Request identifiers and idempotent cancellation.
- Frontend rendering for progress, failures and partial responses.

Acceptance checks:

- Reconnecting or retrying cannot duplicate a user message.
- Cancellation leaves an auditable terminal event.
- Contract tests cover request and event schema compatibility.

Current implementation notes:

- Tauri exposes typed `conversation.start`, `conversation.send` and
  `conversation.cancel` commands to the React shell.
- The Python sidecar accepts authenticated conversation lifecycle requests and
  returns structured response events.
- The current event stream is deterministic placeholder behavior; it proves the
  contract path before connecting the conversation core and operation registry.
- No Git, GitHub, LLM or shell operation is exposed through this contract yet.

### Increment 4: Read-Only Operation Kernel

Goal: introduce the registered operation model without mutation.

Deliverables:

- Operation registry with stable names, typed schemas, risk class and audit
  fields.
- Read-only local operations:
  `project.list`, `project.connect`, `repository.snapshot`, `git.status`,
  `git.branches`, `git.remotes`, `git.history`.
- Policy result shape:
  `allow`, `require_confirmation`, `deny`.
- Operation audit records for observe and prepare operations.

Acceptance checks:

- Conversation can request repository evidence through operation schemas.
- The model cannot emit raw shell as a product operation.
- Cross-project state is explicit in every operation input and result.

Current implementation notes:

- The sidecar registers the initial observe operations:
  `project.list`, `project.connection`, `repository.snapshot`, `git.status`
  and `github.repository.list`.
- `project.register` and `project.connect` mutate only the local application
  registry. They do not change Git remotes or GitHub repositories.
- Operation execution returns normalized JSON through authenticated Tauri IPC.
- Git evidence is collected with fixed subprocess argument lists, not shell
  text supplied by the model or frontend.
- The Projects view consumes these operations for read-only local evidence.

### Increment 5: GitHub Account and Portfolio

Goal: connect GitHub and associate local projects with remote repositories.

Deliverables:

- Guided browser/device authentication.
- Protected credential storage.
- Active account and granted capability display.
- Repository listing and search.
- Local folder to GitHub repository association.
- Offline, permission and rate-limit aware errors.

Acceptance checks:

- A user connects GitHub without manually creating a token.
- Tokens never appear in frontend state, prompts, logs or memory.
- Local and remote identity are visible before association.

Current implementation notes:

- Settings exposes Device Flow authentication and account status.
- Projects can list repositories visible to the connected GitHub account,
  filter them locally and associate one selected repository with the selected
  local project.
- Associations are stored in `project_repository_links` with owner, repository,
  URL, default branch, privacy and account metadata only. Tokens remain in
  platform secure storage.
- Repository listing and project association are typed operations. They do not
  perform remote mutation.

### Increment 6: GitHub Actions Understanding

Goal: make the app useful for explaining automation state and failures.

Deliverables:

- Workflow discovery and normalized workflow models.
- Trigger, permission, job, dependency, environment and secret-reference
  explanation.
- Run, job, step, annotation and log retrieval.
- Failure classification with evidence and confidence.
- Redaction and truncation for logs.

Acceptance checks:

- Diagnoses cite exact workflow evidence.
- Unknown failure causes remain explicitly unknown.
- Secret values are never retrieved or displayed.

### Increment 7: Safe Mutations for Commits and Pull Requests

Goal: move from evidence and drafts to approved local/remote actions.

Deliverables:

- Commit group proposals.
- Commit and branch previews.
- Pull request previews.
- Approved commit, push and PR creation.
- Stale-state invalidation for approvals.

Acceptance checks:

- No local or remote mutation occurs without an approved current preview.
- Account, owner, repository, base and head are visible before PR creation.
- Merge and force push remain unavailable.

### Increment 8: Actions Operation and Release Procedures

Goal: operate workflows and releases with explicit previews.

Deliverables:

- Workflow dispatch forms from typed inputs.
- Approved rerun, cancellation and dispatch.
- Workflow patch previews and validation.
- Release readiness checks and release publication preview.
- Versioned reusable procedures composed only of registered operations.

Acceptance checks:

- Remote operations name repository, workflow, ref and inputs.
- Retrying cannot silently duplicate dispatches.
- Procedures contain no model-supplied raw shell.

## Workstream Ownership

Frontend:

- Conversation, Projects, Activity and Settings surfaces.
- Visual evidence, previews, confirmations and progress.
- Accessibility and keyboard behavior.

Desktop shell:

- Tauri app lifecycle.
- Sidecar startup/shutdown.
- Native folder selection.
- Secure storage integration.
- Packaging and update hooks.

Backend:

- Conversation orchestration.
- Operation kernel and policy.
- Git and GitHub domain adapters.
- Persistence, audit and migrations.
- Credential redaction and data boundaries.

Testing:

- Python unit/integration tests.
- Frontend typecheck, lint and component tests.
- Rust `cargo check` and command tests.
- Desktop smoke tests on clean runtime state.
- Packaging install/uninstall checks.

## Immediate Task Queue

1. Add the minimal desktop workspace.
2. Add contributor commands for frontend and desktop checks.
3. Prove the desktop shell builds without historical screens.
4. Investigate the currently slow/blocking pytest behavior.
5. Implement sidecar health with no product command endpoint.
6. Define the first IPC contract types.
7. Implement read-only local repository operations.

## Known Risks

- The current full pytest run appears slow or blocked and needs isolation.
- Historical desktop code includes screens that conflict with the reduced
  product scope.
- The sidecar lifecycle must avoid exposing a general local HTTP API to
  untrusted origins.
- GitHub OAuth ownership, callback infrastructure and signing strategy are
  deferred decisions.
- Package manager lockfiles may need regeneration once the minimal frontend
  dependency set is finalized.

## Definition of Progress

Progress is measured by shipped capability, not by restored code volume.

Each increment must leave:

- executable checks;
- updated documentation;
- explicit current/transitional/target labeling;
- no credential exposure regression;
- no new end-user workflow exclusive to the TUI.
