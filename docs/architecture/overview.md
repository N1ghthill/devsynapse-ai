# Architecture Overview

## Product Direction

DevSynapse is a packaged conversational desktop copilot for GitHub, GitHub
Actions and repository work.

The target end-user system is:

```text
Tauri desktop shell
    + React conversation interface
    + bundled Python backend
    + typed Git/GitHub operations
    + local SQLite memory and audit
```

The current Textual TUI is a transitional implementation and developer aid. It
is not the target product surface.

## Current System

```text
Textual TUI
    -> DevSynapseBrain
    -> LLM providers
    -> generic command bridge
    -> SQLite memory
```

Useful current components:

- provider transport and routing;
- conversation persistence;
- project registry and resolution;
- explicit and learned user preferences;
- procedural project memory;
- telemetry and operation-like run records;
- Git-aware project context;
- tests and migrations.

Transitional components:

- Textual UI and slash commands;
- shell installer and command wrappers;
- broad Build-mode autoexecution;
- generic command extraction and bridge;
- coding-oriented builder/planner behavior.

## Target System

```text
Desktop application
        |
        v
Conversation and visual evidence
        |
        v
Typed IPC to bundled backend
        |
        v
Conversation orchestration
        |
        v
Operation registry and policy
   +---------+----------+
   |         |          |
 local Git  GitHub API  memory/audit
```

GitHub is a core boundary, not an optional plugin. The application directly
models pull requests, checks, workflows, Actions runs, jobs, logs,
environments and releases.

## Desktop Responsibilities

Tauri:

- lifecycle, packaging and updates;
- bundled backend management;
- secure local IPC;
- OS credential and file-picker integration;
- notifications and platform capabilities.

React:

- conversational interaction;
- onboarding and GitHub connection;
- projects and activity;
- visual evidence, previews and confirmations;
- progressive disclosure and accessibility.

Python core:

- LLM conversation orchestration;
- adaptive preference context;
- Git and GitHub domain services;
- typed operations, policy and approval;
- persistence, migrations and audit;
- credential-safe external adapters.

## Interface Boundary

The target product has four primary destinations:

```text
Conversation
Projects
Activity
Settings
```

Conversation is the home surface. Pull requests, Actions and releases appear
as project context and conversation cards rather than additional permanent
navigation.

Internal provider routing, token telemetry, plugins, skills and agent
components do not become primary end-user interfaces.

## Conversation Adaptation

The existing preference and memory stores provide a starting point, but target
adaptation is explicit:

- experience level;
- detail level;
- tone;
- proactive guidance;
- explanation before confirmation.

Users can inspect, edit and reset these preferences. Adaptation changes
communication only; operation risk and authorization remain deterministic.

## Migration Strategy

1. Recover the historical Tauri/React packaging foundation selectively.
2. Bundle the current Python backend behind private typed IPC.
3. Establish conversation, project and activity desktop shells.
4. Add guided GitHub authentication and repository association.
5. Replace generic shell tools with typed Git and GitHub operations.
6. Deliver Actions understanding, diagnosis and operation.
7. Retire TUI, slash-command and shell-install user flows.

## Architecture Rules

- No target user workflow requires a terminal.
- Frontend code does not parse Git or GitHub responses.
- The model proposes operations but cannot authorize them.
- GitHub credentials never enter prompts or frontend state.
- Consequential operations use current visual previews.
- Explicit user conversation preferences override inferred preferences.
- The application remains responsive during LLM, Git and GitHub work.
- Every persisted schema change uses a migration.
- Packaged clean-machine behavior is a product acceptance criterion.

## Documentation Map

- [Product vision](../product-vision.md)
- [Product contract](../product-contract.md)
- [Desktop operations architecture](repository-operations.md)
- [Desktop foundation plan](../development/desktop-foundation.md)
- [Roadmap](../roadmap.md)
- [Security model](../security/local-security-model.md)
