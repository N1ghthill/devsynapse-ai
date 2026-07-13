# Desktop GitHub Assistant Roadmap

## Objective

Deliver DevSynapse as an installable conversational desktop application that
understands GitHub and GitHub Actions deeply and does not require users to
operate a terminal.

The roadmap intentionally removes general coding-agent, multi-user,
multi-agent, plugin-management and terminal-product work from the critical
path.

## Phase 0: Simplify and Recover the Desktop Foundation

Goal: establish one target product and recover only useful historical assets.

Deliverables:

- packaged desktop and GitHub-first product contract;
- inventory of the historical Tauri/React frontend at pre-removal commit
  `5019c19`;
- selected recovery list for packaging, icons, updater, IPC and accessible UI
  primitives;
- explicit rejection list for login/admin/generic dashboard surfaces;
- simplified navigation: Conversation, Projects, Activity and Settings;
- legacy TUI retirement policy.
- component-by-component scope reduction and removal gates.

Exit criteria:

- no target document describes the TUI as canonical;
- GitHub is consistently a core capability;
- the desktop architecture has one packaging and IPC strategy;
- deferred code is clearly separated from code to recover.

## Phase 1: Packaged Desktop Shell

Goal: launch a self-contained desktop application on a clean machine.

Deliverables:

- restored Tauri 2 + React + TypeScript workspace;
- bundled Python backend sidecar;
- private typed IPC with streaming, progress and cancellation;
- application lifecycle and sidecar health handling;
- native project-folder selection;
- user-scoped runtime directories;
- Linux and Windows development packages;
- production release workflow for Linux `.deb`, Linux AppImage, Windows
  NSIS/MSI artifacts;
- desktop CI for frontend, Rust shell and bundled backend;
- minimal Conversation, Projects, Activity and Settings shells;
- visual AI provider setup with API key entry, model selection and OpenRouter
  free-model discovery.

Exit criteria:

- an artifact installs and launches without Python, Node, Rust or terminal
  setup;
- the backend starts and stops with the application;
- a health failure produces a visual recovery path;
- no login, admin or provider dashboard is restored;
- desktop smoke tests run in CI;
- tagged releases produce installable desktop package artifacts;
- the TUI remains development-only and receives no new product workflow.

## Phase 2: GitHub Connection and Project Portfolio

Goal: connect an account and understand the user's projects safely.

Deliverables:

- guided GitHub browser/device authentication;
- protected credential storage;
- account and granted-capability display;
- repository listing and search; current implementation lists repositories
  visible to the connected account and filters the loaded page locally;
- local-folder to GitHub-repository association; current implementation stores
  the association in the app registry without changing Git remotes;
- typed project, repository and Git status operations;
- project cards with current attention reasons;
- rate-limit, offline and permission-aware errors.

Exit criteria:

- a new user connects GitHub without creating a token manually;
- local and remote repository identity is always visible before association;
- tokens never enter frontend state, prompts, logs or memory;
- the portfolio remains usable with temporarily unavailable GitHub;
- repository evidence does not use model-generated shell commands.

## Phase 3: Adaptive Conversational Core

Goal: make dialogue the primary interface rather than a command prompt.

Deliverables:

- conversation contracts for text, evidence, choices, previews and progress;
- onboarding for experience level, detail, tone and proactive guidance;
- visible conversation preference controls;
- conservative preference learning with evidence and confidence;
- edit, forget and reset controls;
- prompts centered on GitHub collaboration rather than code implementation;
- contextual explanations for Git, GitHub and Actions terminology;
- tests for beginner, working-developer and expert interaction profiles.

Exit criteria:

- explicit preferences consistently override learned preferences;
- adaptation changes explanation, not facts or authorization;
- the assistant asks focused questions when ambiguity matters;
- users can inspect and remove learned conversational preferences;
- responses can be dialogical and explanatory without blocking experts who
  prefer brevity;
- the UI does not require slash commands.

## Phase 4: GitHub Actions Understanding and Diagnosis

Goal: make DevSynapse exceptionally capable at explaining why automation works
or fails.

Deliverables:

- workflow discovery, parsing and visual explanation;
- trigger, permission, job, dependency, environment and secret-reference
  models;
- Actions run, job, step, check, annotation and log retrieval;
- failure classification with evidence and confidence;
- correlation with commits and pull requests;
- guided recovery recommendations;
- safe log truncation and credential redaction.

Exit criteria:

- the assistant can explain a workflow to a beginner and expose raw detail to
  an expert;
- common syntax, dependency, test, permission, secret/environment, runner and
  transient failures have fixture coverage;
- diagnoses cite exact jobs, steps, annotations or log evidence;
- unknown failures remain explicitly unknown;
- no secret value is retrieved or displayed.

## Phase 5: Commits, Branches and Pull Requests

Goal: guide changes from a local worktree into a reviewable GitHub pull request.

Deliverables:

- coherent commit-group proposals;
- commit-message convention learning;
- previews for staging, branch creation and commits;
- branch synchronization and readiness explanation;
- pull request title and description preparation;
- checks, reviews and unresolved-conversation summaries;
- approved push and pull request creation;
- immutable previews and stale-state invalidation.

Exit criteria:

- no local or remote mutation occurs without an approved current preview;
- unrelated changes can be separated clearly;
- the active account, repository, base and head are visible;
- hook, push and PR failures have recovery paths;
- merge and force push remain unavailable.

## Phase 6: GitHub Actions Authoring and Operation

Goal: safely create, improve and operate workflows through conversation.

Deliverables:

- guided workflow creation from intended outcomes;
- previewed workflow patches;
- validation of syntax, permissions and referenced actions;
- workflow input forms generated from dispatch definitions;
- approved dispatch, rerun and cancellation operations;
- run monitoring and desktop notifications;
- environment and permission guidance;
- before/after explanation for workflow changes.

Exit criteria:

- users can create a basic workflow without manually authoring YAML;
- generated workflows use minimal permissions and pinned references according
  to product policy;
- every remote operation names repository, workflow, ref and inputs;
- retries cannot silently duplicate dispatches;
- resulting runs are verified and linked back into conversation.

## Phase 7: Releases and Reusable Procedures

Goal: automate repeated repository work without becoming opaque.

Deliverables:

- release readiness and changelog preparation;
- previewed release publication;
- versioned procedures composed only of registered operations;
- dry-run and full-procedure preview;
- explicit local and remote approval points;
- resumable execution and partial-failure recovery;
- project-scoped, expiring trust options for low-risk repeated operations.

Exit criteria:

- procedures contain no raw shell supplied by the model;
- trust cannot cross account, repository or project boundaries;
- partial completion is visible and recoverable;
- releases verify checks, tags and target before publication.

## Retirement Phase

The TUI, slash-command catalog, shell installer and generic model command bridge
can be removed from release scope when:

- desktop packaging and updates are stable;
- account, project and provider setup exist visually;
- conversation uses typed operations;
- migration preserves supported local data;
- desktop diagnostics cover the development cases previously handled in the
  terminal.

They may remain temporarily as internal developer tools, but must not shape
product APIs or user documentation.

## Cross-Cutting Requirements

Every phase includes:

- accessibility and keyboard support;
- progressive disclosure for different experience levels;
- typed IPC and operation contracts;
- credential redaction;
- cancellation, timeout and offline behavior;
- migrations for persisted state;
- deterministic policy and audit;
- clean-machine packaging tests;
- documentation distinguishing current and target behavior.

## Immediate Implementation Sequence

The first implementation milestone is divided into four reviewable pull
requests:

1. Restore the minimal Tauri/React workspace, icons and build configuration
   without historical screens.
2. Bundle the existing Python backend and prove private IPC health,
   start/stop, streaming and cancellation.
3. Add the operation kernel plus read-only Git/GitHub account capability
   contracts.
4. Deliver a packaged conversation shell with visual onboarding and project
   selection.

The detailed plan is in
[the desktop foundation implementation plan](development/desktop-foundation.md).

## Deferred Until Evidence Exists

- macOS distribution is out of scope;
- exact OAuth deployment ownership and callback infrastructure;
- optional offline-only mode;
- organization and enterprise GitHub features;
- automatic health scoring across portfolios;
- multi-repository procedures;
- whether the Python sidecar remains long-term.

These decisions do not block the packaged desktop foundation.
