# Desktop Repository Operations Architecture

## Status

This is the target architecture. The current v1 TUI and generic command bridge
are transitional.

## System Shape

```text
Packaged Tauri desktop application
  React conversation and project interface
                    |
             typed local IPC
                    |
        bundled DevSynapse backend
                    |
      conversation orchestration
                    |
             operation service
       +------------+-------------+
       |            |             |
   local Git    GitHub API    local memory
    adapter      adapter        and audit
       +------------+-------------+
                    |
       previews, approvals, results
```

The desktop application is the only target end-user interface. The backend is
not a separately managed service and does not require the user to operate a
terminal.

## Desktop Boundary

The target stack is:

- Tauri 2 desktop shell;
- React and TypeScript interface;
- bundled Python backend sidecar during the transition;
- signed, versioned OS-specific release artifacts.

The repository previously shipped this general stack. Historical code is a
reference and source of reusable packaging assets, not the target information
architecture.

The desktop shell owns:

- application lifecycle and updates;
- secure backend process startup and shutdown;
- OS credential-store integration;
- file and folder selection;
- external browser authentication handoff;
- desktop notifications;
- platform packaging.

The React interface owns:

- conversation presentation and input;
- onboarding and GitHub connection;
- project navigation;
- visual evidence;
- operation previews and confirmations;
- progressive disclosure of technical details;
- accessibility and responsive layout.

The Python backend owns domain behavior. The frontend must not implement Git,
GitHub policy or authorization rules.

## Conversation Layer

The conversation layer:

- interprets user intent;
- selects relevant projects and GitHub objects;
- requests evidence through typed operations;
- maintains dialogue and project context;
- adapts language, detail and pace;
- explains observations and uncertainty;
- proposes actions and asks focused questions.

It does not:

- authorize its own proposal;
- execute raw shell text;
- handle GitHub tokens;
- infer operation risk;
- report success before verification.

Conversation responses can include structured cards:

```text
ProjectSummary
PullRequestSummary
WorkflowExplanation
ActionsFailure
ChangeGroupProposal
OperationPreview
OperationProgress
OperationResult
ClarifyingChoice
```

Cards support dialogue; they do not turn the product into a static dashboard.

## Conversation Adaptation

The current backend already supplies user preferences, project memory,
procedural memory and learned signals to the prompt. The target makes this
explicit and controllable.

The preference model separates:

- experience level;
- desired detail;
- communication tone;
- proactive guidance;
- explanation required before confirmation.

Preference sources are:

```text
explicit
confirmed_inference
temporary_session
```

Raw implicit guesses are not durable until repeated or confirmed. The settings
screen shows learned preferences, confidence and reset controls. Adaptation
changes communication, not security, approval or factual evidence.

## Operation Kernel

Every operation definition declares:

- stable name;
- typed input and result schemas;
- risk class;
- required local and remote identity;
- preview behavior;
- policy checks;
- executor;
- timeout and cancellation behavior;
- audit fields;
- idempotency and retry rules.

Initial families:

```text
account.connect
account.status
project.list
project.connect
repository.snapshot
git.status
git.history
git.branches
git.remotes
commit.propose_groups
commit.preview
commit.stage
commit.create
pull_request.inspect
pull_request.preview
pull_request.create
workflow.list
workflow.explain
workflow.validate
workflow.preview_change
actions.runs
actions.run_detail
actions.failure_diagnosis
actions.rerun
actions.cancel
actions.dispatch
release.preview
release.publish
```

The model sees operation schemas, not shell commands or GitHub HTTP endpoints.

## GitHub Domain

GitHub is a primary domain boundary. The backend models:

- authenticated account and granted capabilities;
- repository and remote association;
- branches, commits and comparisons;
- issues and pull requests;
- reviews, conversations, checks and merge requirements;
- workflow definitions, triggers, permissions and inputs;
- Actions runs, jobs, steps, annotations, logs and artifacts;
- environments, protected deployment gates and secrets metadata;
- releases, tags and assets.

Secret values are never retrieved for explanation. The application can explain
that a secret is missing or referenced, but cannot display its value.

The adapter uses the GitHub API directly. The user is not required to install
or understand the `gh` CLI. A developer-only adapter may use fixtures or
recorded responses, but product behavior is based on normalized domain
contracts.

## GitHub Actions Expertise

Actions support has four layers:

1. Understand: parse and explain workflows, triggers, jobs and permissions.
2. Validate: detect syntax, reference, permission and configuration problems.
3. Diagnose: correlate run logs, annotations, repository changes and known
   failure classes.
4. Operate: preview and execute reruns, cancellations, dispatches and approved
   workflow changes.

Diagnosis produces evidence and confidence, not invented certainty. Stable
failure categories include:

```text
workflow_syntax
action_reference
dependency
test_or_build
permission
secret_or_environment
runner_environment
rate_limit
network_or_service
cancelled
unknown
```

## Policy and Approval

The policy engine returns:

```text
allow
require_confirmation
deny
```

Required inputs include:

- operation metadata;
- selected local project;
- active GitHub account;
- owner and repository;
- branch, pull request, workflow or run target;
- current-state fingerprint;
- credential capability;
- protected-resource rules.

Consequential operations create immutable previews. Execution fails closed if
the local or remote state changed, the account changed or the preview expired.

## Desktop Information Architecture

Keep navigation small:

```text
Conversation
Projects
Activity
Settings
```

- Conversation is the home surface.
- Projects provides portfolio and repository context.
- Activity contains approvals, running operations and history.
- Settings contains account, conversation, privacy and advanced diagnostics.

Pull requests, Actions and releases are contextual project views and
conversation cards, not permanent top-level sections.

Provider models, token telemetry, skills, plugins and internal routing are not
primary navigation.

## Local IPC and Sidecar

The desktop shell starts exactly one backend sidecar for the signed application
bundle. The IPC design must:

- bind only to the local application;
- authenticate requests if loopback HTTP is used;
- reject arbitrary origins;
- use typed request and event contracts;
- stream conversation and operation progress;
- support cancellation;
- redact logs;
- terminate the sidecar with the application.

Prefer Tauri IPC or a private local channel. A loopback server is acceptable
only with an ephemeral port, per-launch secret and strict origin controls.

## Credential Storage

GitHub and provider credentials are handled by the backend and platform secure
storage. They never enter React state beyond non-secret account metadata.

Authentication should use a guided browser or device flow suitable for a
desktop application. Manual token entry may exist as an advanced fallback, not
the first-run default.

## Packaging and Updates

Release engineering must cover:

- reproducible frontend and bundled-backend builds;
- Linux and Windows artifacts;
- no macOS distribution target;
- code signing where the platform requires it;
- update metadata and rollback;
- migration compatibility;
- first-launch health checks;
- uninstall and retained-data choices.

Normal users install an artifact. Source-based shell installation remains
development-only during migration.

## Suggested Target Layout

```text
frontend/
  src/
    app/
    conversation/
    projects/
    activity/
    settings/
    components/
    contracts/
  src-tauri/
core/
  conversation/
  operations/
  repositories/
  git/
  github/
  memory/
```

Do not restore historical `Admin`, multi-user `Login`, generic `Dashboard` or
provider-monitoring pages.

## Transition Map

| Current component | Direction |
|---|---|
| Textual TUI | keep temporarily for development; retire from releases |
| shell installer and wrappers | replace with packaged artifacts and desktop updates |
| `DevSynapseBrain` | retain useful conversation orchestration; adopt operation proposals and adaptive dialogue |
| `OpenCodeBridge` | remove from normal model tools; no shell console in target UI |
| command extraction | retire after typed operation coverage |
| project resolver | retain and strengthen canonical local/remote identity |
| memory stores | retain; simplify around conversations, preferences, projects and operations |
| provider routing | keep internal; remove from primary UX |
| plugin/skill systems | keep only if used internally; do not expose during initial desktop scope |
| historical Tauri frontend | recover packaging and useful components selectively |

## Testing Strategy

Required layers:

- unit tests for operation schemas, policies and parsers;
- temporary-repository Git integration tests;
- GitHub contract tests with fixtures;
- Actions workflow and failure-classification fixtures;
- IPC contract tests;
- React component and accessibility tests;
- desktop smoke tests against a bundled sidecar;
- packaging and clean-machine installation tests;
- stale-preview and cross-project safety tests;
- preference adaptation tests proving explicit settings win;
- tests proving credentials never reach prompts, logs or frontend payloads.

Normal verification does not require live GitHub or paid LLM calls.

## Completion Criteria

The target architecture is complete when:

- a new user installs and connects GitHub without a terminal;
- the packaged app is the only documented end-user surface;
- normal conversation uses typed Git and GitHub operations;
- Actions runs can be explained, diagnosed and safely operated;
- communication adapts through visible user-controlled preferences;
- all mutations use previews and deterministic policy;
- credentials remain outside prompts and frontend state;
- TUI, slash-command and generic shell paths are absent from release artifacts.
