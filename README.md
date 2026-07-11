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

The current `main` branch contains the Python core, the transitional Textual
TUI and the recovered desktop foundation for the target product.

Current desktop capabilities:

- Tauri 2 + React/TypeScript shell with Conversation, Projects, Activity and
  Settings;
- bundled Python sidecar lifecycle in development and packaged-sidecar build
  support;
- authenticated private loopback IPC for typed conversation and operations;
- native project-folder picker and local project registry;
- read-only repository evidence operations: `project.list`,
  `repository.snapshot` and `git.status`;
- `commit.preview` prepare operation with state fingerprint evidence;
- GitHub OAuth Device Flow contracts in Settings:
  `github.auth.start`, `github.auth.poll`, `github.account.status` and
  `github.auth.disconnect`;
- real Tauri window smoke included in `make verify` when a graphical display or
  `xvfb-run` is available.

GitHub connection requires `GITHUB_CLIENT_ID` from an OAuth App or GitHub App
with Device Flow enabled. The token is stored through the platform keyring and
is never returned to the frontend.

Not yet complete:

- installable release artifacts for normal users;
- repository listing/search through GitHub API;
- local-to-remote repository association;
- approved local or remote mutation execution.

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
- Node.js and npm for the desktop frontend;
- Rust toolchain for the Tauri shell;
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

Run the desktop shell in development:

```bash
cd frontend
npm install
npm run tauri:dev
```

Enable GitHub Device Flow in the desktop Settings screen by configuring:

```bash
GITHUB_CLIENT_ID=your_oauth_app_client_id
```

## Repository Structure

```text
config/            current runtime settings
core/              conversation, memory, policy and transitional tools
devsynapse/        transitional Textual interface
docs/              product, architecture, security and implementation plans
frontend/          Tauri 2 + React/TypeScript desktop shell
plugins/           existing extension example; not target product UI
scripts/           current installation, migration and evaluation utilities
tests/             unit and integration tests
```

## Verification

Current baseline:

```bash
make verify
```

The verification surface currently includes Python tests and Ruff, frontend
lint/build, Rust `cargo check`, script checks, TUI smoke and a short Tauri
window smoke. Clean-machine package installation checks remain future release
work.

## Contribution Contract

Before implementation, read [AGENTS.md](AGENTS.md). Changes must:

- preserve the distinction between current and target behavior;
- use typed Git/GitHub operations instead of model-generated shell;
- keep GitHub credentials out of prompts, logs, memory and frontend state;
- include migrations for persisted schema changes;
- update the nearest product or architecture document;
- pass the relevant current and desktop verification surfaces.
