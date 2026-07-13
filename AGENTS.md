# Repository Guidelines

## Project Structure & Architecture

DevSynapse AI is a packaged conversational desktop assistant for GitHub, GitHub
Actions and repository work. The target stack is Tauri 2 + React/TypeScript
with a bundled Python backend. `core/` holds current conversation,
persistence, routing and transitional execution logic; `devsynapse/` is the
transitional Textual interface; `config/` holds current settings. Tests live in
`tests/unit/` and `tests/integration/`; docs in `docs/`.

The TUI, slash commands, shell installer and generic command bridge are
transitional. Do not add new end-user workflows exclusively to them. New
product workflows use typed Git/GitHub operations with deterministic risk,
visual previews, approvals and audit results. Read
[docs/product-vision.md](docs/product-vision.md),
[docs/architecture/repository-operations.md](docs/architecture/repository-operations.md)
and [docs/roadmap.md](docs/roadmap.md) before adding a product capability.

Key core modules:
- `brain.py` — LLM orchestration and auto-execution loop.
- `deepseek.py` — API transport; returns `LLMResult` dataclass, not raw dicts.
- `routing.py` — `RouteSelector` for model selection and budget-aware routing (extracted from brain).
- `prompts.py` — system prompt template builder (extracted from brain).
- `correlation.py` — request, conversation and tool-run ID generators.

Keep desktop UI, IPC, conversation, Git/GitHub domain logic, policy,
persistence and external adapters separate. Conversation may propose
operations but must not determine authorization. Frontend code must not receive
credentials or parse raw Git/GitHub responses.

The target operator flow is an installed desktop application with Conversation,
Projects, Activity and Settings. Normal users must not need a terminal,
development runtime, source checkout, `gh` CLI or slash commands. The current
`devsynapse` TUI remains available only for migration and backend development.

## Documentation & Contract Discipline

Documentation is part of the runtime contract. If a change affects behavior,
desktop contracts, setup, migrations, GitHub operations or roadmap acceptance
criteria, update the nearest relevant doc in the same change. Label
capabilities as current, transitional or target. Schema changes require
explicit migrations and data model docs.

## Build, Test, and Development Commands

Use the root `Makefile`:

- `make install-dev`: install Python dev dependencies.
- `make run`: start the transitional TUI for current-core development.
- `make lint`: run Ruff.
- `make test`: run pytest.
- `make tui-smoke`: check the transitional TUI while it remains in the tree.
- `make verify`: run lint, tests, script checks, and TUI smoke checks.
- `make migrate` / `make migration-status`: apply or inspect migrations.

## Coding Style & Naming Conventions

CI uses Python `3.13`; Ruff targets `py310` syntax with 100-character lines, double quotes, space indentation, and import sorting. Keep modules small and explicit, especially around authorization, persistence, and command execution. Tests and Python modules use `snake_case`. Avoid cross-layer shortcuts or duplicated business rules.

## Testing Guidelines

Pytest discovers `test_*.py`, `Test*` classes, and `test_*` functions under
`tests/`. Use markers (`unit`, `integration`, `slow`, `e2e`) when useful. Add
or update tests for migrations, authorization, persistence, IPC and Git/GitHub
contracts. Desktop work also requires frontend, Rust, accessibility, smoke and
packaging tests. Run focused tests such as
`./venv/bin/pytest -q tests/unit/test_memory.py`.

## Commit & Pull Request Guidelines

Recent history uses prefixes such as `feat:`, `docs:`, and `chore:`; follow that pattern with concise, imperative summaries. Pull requests should state the problem, approach, validation performed, and documentation updates.

## Security & Configuration Tips

Start from `.env.example` for current backend development and keep provider or
GitHub credentials out of commits, prompts, memories, logs and frontend state.
Target desktop credentials use platform secure storage. The legacy bridge is
not a hardened sandbox. New operations must be typed, project-aware, auditable,
tested and assigned a deterministic risk class. Local and remote mutations
require separate policy decisions.
