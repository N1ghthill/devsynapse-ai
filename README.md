# DevSynapse AI

DevSynapse AI is a conversational desktop copilot for GitHub, GitHub Actions
and repository work.

It helps new and experienced developers understand projects, diagnose
automation, prepare commits and pull requests and safely operate GitHub through
natural dialogue and visual, reviewable actions.

## Product Direction

The target product is an installed desktop application:

- no terminal required for normal use;
- guided GitHub connection;
- conversation as the primary interface;
- project and repository context;
- deep GitHub Actions understanding and diagnosis;
- visual previews before local or remote mutations;
- adaptive explanations for beginner through expert users;
- packaged runtime and application updates.

GitHub is a core product capability, not an optional integration. The assistant
models pull requests, checks, workflows, runs, jobs, logs, environments and
releases rather than forwarding raw CLI output.

Read:

- [product vision](docs/product-vision.md);
- [product contract](docs/product-contract.md);
- [desktop architecture](docs/architecture/repository-operations.md);
- [roadmap](docs/roadmap.md);
- [desktop foundation plan](docs/development/desktop-foundation.md).

## Current Status

The current `main` branch contains the Python core and a transitional Textual
TUI. It does not yet ship the new desktop product or complete GitHub
integration.

The repository history contains a previous Tauri 2/React/TypeScript desktop
application with bundled backend and Windows/Linux packaging. The roadmap
recovers that foundation selectively without restoring its former admin,
multi-user and generic dashboard surfaces.

New product work should target the packaged desktop architecture. Do not add
new end-user workflows exclusively to the TUI, slash-command catalog or generic
command bridge.

## Focus

DevSynapse will:

- connect GitHub accounts through a guided desktop flow;
- organize local and GitHub projects;
- explain Git state and propose coherent commits;
- prepare and create approved pull requests;
- explain and validate GitHub Actions workflows;
- diagnose failed runs using jobs, annotations and logs;
- safely dispatch, rerun and cancel approved workflows;
- prepare releases and reusable repository procedures;
- adapt tone, detail and terminology under user control.

DevSynapse is not:

- a general coding agent or IDE;
- a terminal frontend or shell assistant;
- an analytics dashboard;
- a provider/model control panel;
- a multi-user administration system;
- an autonomous merge or deployment authority;
- a plugin or multi-agent construction kit.

## Product Architecture

```text
Tauri desktop application
  React conversation and project interface
                    |
             private typed IPC
                    |
        bundled Python backend
                    |
      conversation + operation policy
          |                    |
      local Git            GitHub API
          +---------+----------+
                    |
          SQLite memory and audit
```

The model interprets intent and maintains dialogue. Deterministic backend
services own GitHub identity, operation risk, previews, approvals and
execution.

## Conversation Adaptation

The current backend already stores user preferences and supplies preferences,
project memory and learned signals to the model. The target desktop product
makes this capability explicit and user-controlled:

- experience level;
- detail level;
- communication tone;
- proactive guidance;
- explanation before confirmation.

Users can inspect, edit and reset learned preferences. Adaptation never changes
security or confirmation requirements.

## Development

Current backend prerequisites:

- Python 3.10 or newer;
- Linux or another Unix-like development environment;
- Git.

Set up the current core:

```bash
python3 -m venv venv
source venv/bin/activate
make install-dev
make verify
```

Run the transitional TUI for current-core development:

```bash
make run
```

This is a contributor workflow, not the target end-user installation.

## Repository Structure

```text
config/            current runtime settings
core/              conversation, memory, policy and transitional tools
devsynapse/        transitional Textual interface
docs/              product, architecture, security and implementation plans
plugins/           existing extension example; not target product UI
scripts/           current installation, migration and evaluation utilities
tests/             unit and integration tests
```

The roadmap will restore a minimal `frontend/` Tauri/React workspace.

## Verification

Current baseline:

```bash
make verify
```

Desktop work will add frontend lint/typecheck, Rust tests, IPC contracts,
desktop smoke tests and clean-machine package installation checks.

## Contribution Contract

Before implementation, read [AGENTS.md](AGENTS.md). Changes must:

- preserve the distinction between current and target behavior;
- use typed Git/GitHub operations instead of model-generated shell;
- keep GitHub credentials out of prompts, logs, memory and frontend state;
- include migrations for persisted schema changes;
- update the nearest product or architecture document;
- pass the relevant current and desktop verification surfaces.
