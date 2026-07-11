# Product Contract

## Identity

DevSynapse AI is a packaged, conversational desktop copilot for GitHub, GitHub
Actions and repository work.

Its product value is GitHub expertise delivered through natural dialogue,
visual evidence and safely executed operations. It is not a terminal product or
a general coding agent.

## Target Product Surface

The target user installs and launches one desktop application. That application
owns:

- first-run orientation;
- GitHub account connection;
- local project selection;
- conversation;
- project and repository context;
- pull request and GitHub Actions evidence;
- operation previews and confirmations;
- progress, results and recovery;
- conversation and privacy preferences;
- application updates.

Normal operation must not require a terminal, development runtime, source
checkout, `gh` CLI, slash commands or manual environment files.

## Conversation Contract

DevSynapse:

- responds conversationally rather than as a command dispatcher;
- adjusts terminology, depth and pace to explicit user preferences;
- can infer preferences conservatively from repeated evidence;
- lets the user inspect, change and reset learned preferences;
- asks focused questions when repository, target or risk is ambiguous;
- separates observed state, interpretation and recommendation;
- embeds evidence and action previews in the conversation;
- confirms local and remote mutations in plain language;
- does not claim an action completed until the backend verifies it.

The initial preference profile includes:

```text
experience_level
detail_level
communication_tone
proactive_guidance
confirmation_explanation
```

Explicit settings override inferred values. Security policy never adapts to
conversation style.

## GitHub Contract

GitHub is a core service boundary. DevSynapse must:

- authenticate through a guided desktop flow;
- show the active account;
- identify owner and repository before remote operations;
- use least-privilege credentials and protected storage;
- support rate-limit, offline and permission-aware errors;
- keep tokens and secret values out of prompts, logs and memory;
- model repositories, branches, pull requests, checks, workflows, runs, jobs,
  annotations, environments and releases as domain objects;
- normalize GitHub API responses before they reach conversation or UI code.

GitHub Actions support includes understanding, authoring, validation,
monitoring, diagnosis and approved operation. It must not be reduced to showing
a run status.

## Operation Contract

All normal Git and GitHub work uses registered typed operations.

- Observe operations may run automatically.
- Prepare operations may generate drafts and previews without mutation.
- Local mutations require a current project preview and confirmation.
- Remote mutations require account, owner, repository, target, preview and
  confirmation.
- Destructive operations are unavailable by default.

Approvals bind to immutable previews and current state. A changed repository,
branch, remote or workflow invalidates the approval.

## Scope Reduction

The target end-user application does not expose:

- the Textual TUI;
- slash commands;
- generic shell execution;
- provider selection or token-cost dashboards as primary product navigation;
- multi-user login, admin roles or permission-management screens;
- plugin, skill or multi-agent configuration;
- autonomous coding, merging or deployment.

Provider routing, telemetry, memory and extension code may remain internal when
they directly support conversation quality, reliability or GitHub operations.

## Packaging Contract

Release artifacts must:

- install through normal operating-system flows;
- include the required application runtime;
- launch from the desktop/application menu;
- create user-scoped config, data and log locations automatically;
- guide GitHub and provider setup visually;
- update without requiring Git commands or a source checkout;
- uninstall without leaving executable processes;
- preserve user data only through an explicit, documented choice.

The initial desktop stack is Tauri 2, React and TypeScript with the Python core
bundled as a sidecar. Provider API key and model selection belong in Settings
and do not expose stored secrets to frontend state after saving. Supported
release targets are Linux and Windows; macOS is not distributed.

## Current v1 Transitional Surface

The repository currently ships a Python/Textual TUI:

```bash
devsynapse
devsynapse --version
update-devsynapse
uninstall-devsynapse
```

It contains slash commands and a generic command bridge. These remain available
only while the desktop application and typed operations are implemented.

Current v1 behavior must be documented as transitional. New end-user workflows
must not be added exclusively to the TUI or generic shell bridge.

## Historical Desktop Assets

Git history before commit `1363777` contains a Tauri 2/React/TypeScript
frontend, bundled Python backend support, icons and Windows/Linux release work.

These assets should be recovered selectively. The former login, admin,
monitoring and generic dashboard surfaces are not automatically restored
because they conflict with the simplified single-user product.

## Project Identity

Every local project and GitHub repository association has a stable identity.
A mutation scoped to one project cannot affect another without an explicit
context switch and new preview.

Remote identity includes:

```text
github_account
owner
repository
remote_name
default_branch
```

The UI presents these fields in user-friendly language and makes their
technical details available through progressive disclosure.

## Runtime Data

Runtime data remains user-scoped and local by default:

- application preferences;
- encrypted or OS-protected credential references;
- project registry and GitHub associations;
- conversations;
- explicit and learned user preferences;
- operation proposals, approvals and audit records;
- cached remote evidence with capture times.

Every persisted schema change requires a migration. Conversation retention and
learned preference controls must be visible in the desktop settings.

## Documentation Discipline

Capabilities are labeled:

- current: available in the present v1 TUI;
- transitional: retained only during migration;
- target: required by a roadmap phase but not yet shipped.

No desktop, GitHub or GitHub Actions capability may be advertised as shipped
before its packaging, security, accessibility and acceptance tests pass.
