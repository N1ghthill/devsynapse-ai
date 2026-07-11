# Desktop Foundation Implementation Plan

## Objective

Restore a minimal, packaged DevSynapse desktop application without restoring
the former product's unnecessary screens or exposing the current TUI.

The milestone proves:

```text
installed desktop app
    -> starts bundled backend
    -> establishes private typed IPC
    -> renders a conversation shell
    -> selects a local project
    -> streams a verified backend response
    -> shuts down cleanly
```

GitHub authentication and full repository operations follow after this
foundation, but their contracts influence the boundary now.

## Historical Source

Commit `5019c19` contains the last frontend before the TUI-only refactor:

- Tauri 2 shell;
- React 19 + TypeScript + Vite;
- packaged Python sidecar;
- application icons;
- Linux and Windows packaging;
- updater configuration;
- UI smoke tooling.

Recover these selectively through normal Git history inspection. Do not revert
the TUI refactor wholesale.

## Recover

- `frontend/src-tauri` build skeleton and platform bundle configuration;
- icons and application identifier;
- React/TypeScript/Vite build setup;
- updater and sidecar build concepts after security review;
- useful chat rendering, streaming and error-boundary primitives;
- existing smoke-test ideas;
- CI knowledge from historical desktop release commits.

## Do Not Recover

- multi-user login and JWT session flows;
- admin and role-management screens;
- generic monitoring dashboard;
- knowledge/plugin administration;
- provider/token telemetry as primary UI;
- old route structure;
- raw command execution controls;
- historical CSS wholesale;
- browser-server deployment assumptions.

## Target Navigation

Only four primary destinations:

```text
Conversation
Projects
Activity
Settings
```

The first milestone implements Conversation and enough Settings/Projects shell
to complete onboarding and select a folder. Activity may initially show only
backend connection and operation events.

## Proposed Repository Layout

```text
frontend/
  package.json
  vite.config.ts
  src/
    app/
    conversation/
    projects/
    activity/
    settings/
    components/
    contracts/
  src-tauri/
    capabilities/
    icons/
    src/
scripts/
  build-backend.sh
```

Frontend contracts must be generated from or tested against backend schemas.
Do not maintain unrelated handwritten payload definitions in both languages.

Current implementation notes:

- `backend-entry.py` is only the packaged sidecar entry point.
- `core/desktop_sidecar.py` owns the private authenticated loopback HTTP
  lifecycle used by the Tauri shell.
- `core/desktop_conversation.py` adapts desktop conversation requests to the
  current core and returns a desktop-specific setup message when no provider is
  configured.
- `core/operations.py` owns the registered operation kernel. It currently
  supports read-only project/repository evidence, `project.register`, which
  mutates only the local app project registry, and `commit.preview`, which
  builds immutable state evidence for future commit approval.
- GitHub repository portfolio operations are available as typed contracts:
  `github.repository.list` observes repositories visible to the connected
  account, `project.connect` stores a local project to GitHub repository
  association and `project.connection` returns the stored association.
- `scripts/desktop-smoke.sh` runs a short Tauri window smoke when a graphical
  display or `xvfb-run` is available.
- GitHub connection uses OAuth Device Flow through typed operations
  (`github.auth.start`, `github.auth.poll`, `github.account.status` and
  `github.auth.disconnect`). It requires `GITHUB_CLIENT_ID` for an OAuth App or
  GitHub App with Device Flow enabled. Tokens are stored through the platform
  keyring and are never returned to the frontend.
- AI provider setup is a desktop Settings flow backed by typed operations
  (`llm.provider.status`, `llm.provider.configure` and `llm.model.discover`).
  OpenRouter is the default provider, `openrouter/free` is the default model,
  and provider API keys are written only to the backend runtime config.
- the Projects view persists the last selected local project as a local UI
  preference, can choose a folder through a native dialog and reuses the
  selection when the configured project list is loaded again. It can also load
  GitHub repositories for the connected account and associate one repository
  with the selected local project without changing Git remotes.

## IPC Contract

Minimum messages:

```text
app.health
app.version
conversation.start
conversation.send
conversation.cancel
conversation.event
project.choose_folder
project.register
project.list
```

Streaming events:

```text
response.started
response.delta
response.completed
response.failed
operation.started
operation.progress
operation.completed
operation.failed
```

Every request carries a request identifier. Cancellation and completion are
idempotent. Frontend reconnection cannot duplicate a user message or operation.

## Sidecar Security

- launch only the sidecar shipped with the signed application;
- use Tauri IPC or an authenticated private local channel;
- if loopback HTTP is temporarily retained, choose an ephemeral port and
  per-launch secret;
- reject non-application origins;
- expose no generic command endpoint;
- redact provider and future GitHub credentials;
- stop child processes when the application exits;
- place logs in user-scoped application state.

## Packaged User Experience

First launch:

1. Welcome the user in plain language.
2. Ask experience and conversation preferences.
3. Explain that GitHub connection is the next product step if not implemented
   in the current milestone.
4. Allow selection of an existing local project through a native picker.
5. Open the conversation with the selected project visible.

No step asks the user to open a terminal, edit `.env`, run an installer script
or learn a slash command.

## Pull Request Sequence

### PR 1: Minimal desktop workspace

- restore Tauri/React build skeleton;
- keep only a minimal app shell;
- restore icons and identifier;
- add frontend lint, typecheck and build;
- add development instructions for contributors.

### PR 2: Bundled backend lifecycle

- restore/rebuild the Python sidecar packaging script;
- implement health and version contracts;
- manage start, crash and shutdown;
- create isolated runtime directories;
- add redaction and lifecycle tests.

### PR 3: Typed streaming IPC

- define request and event schemas;
- implement send, stream and cancel;
- render connection and failure states;
- prove the frontend has no generic shell endpoint;
- add contract and reconnection tests.

### PR 4: Conversation-first shell

- implement visual onboarding preferences;
- implement conversation layout and structured event rendering;
- add native project folder selection;
- add minimal Projects, Activity and Settings views;
- add accessibility and desktop smoke tests;
- produce installable Linux and Windows development artifacts.

## Test Matrix

- clean machine without Python/Node/Rust;
- backend starts, responds and exits;
- backend startup timeout and crash;
- application restart with existing runtime data;
- streaming interruption and cancellation;
- frontend reconnection without duplicate messages;
- runtime path containing spaces and non-ASCII characters;
- project folder selection and invalid folder;
- secrets absent from frontend messages and logs;
- keyboard-only onboarding and conversation;
- screen widths at supported minimum;
- Linux package install/uninstall;
- Windows current-user install/uninstall.

## Definition of Done

- an installable artifact launches from the OS application menu;
- users perform first launch and project selection without a terminal;
- the backend is bundled and private to the application;
- conversation streams through typed IPC;
- application failures have visual recovery;
- only the four target navigation areas exist;
- no historical admin/dashboard surface returns;
- contributor verification covers Python, React, Rust and desktop smoke tests;
- target documentation no longer instructs end users to use the TUI.
