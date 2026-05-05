# Repository Guidelines

## Project Structure & Architecture

DevSynapse AI is a local-first TUI + SQLite coding agent. `devsynapse/` holds the terminal UI launcher and Textual app; `core/` holds business logic, persistence, routing, migrations, plugins, and command execution; `config/` holds settings. Tests live in `tests/unit/` and `tests/integration/`; docs in `docs/`; scripts in `scripts/`; plugins in `plugins/`.

Key core modules:
- `brain.py` — LLM orchestration and auto-execution loop.
- `deepseek.py` — API transport; returns `LLMResult` dataclass, not raw dicts.
- `routing.py` — `RouteSelector` for model selection and budget-aware routing (extracted from brain).
- `prompts.py` — system prompt template builder (extracted from brain).
- `correlation.py` — request, conversation and tool-run ID generators.

Keep TUI transport, core logic, persistence and command execution separate. The TUI calls shared core services directly.

Canonical operator flow: `devsynapse` opens the Textual TUI. All product
operations happen inside that TUI through slash commands such as `/connect`,
`/providers`, `/status`, `/usage`, `/budget` and `/router`. Do not add external
operator subcommands such as `devsynapse providers` or alternate default
surfaces unless the product direction explicitly changes.

## Documentation & Contract Discipline

Documentation is part of the runtime contract. If a change affects behavior, TUI commands, setup, migrations, telemetry, or operations, update the nearest relevant doc in the same change. Schema changes require explicit migrations and data model docs.

## Build, Test, and Development Commands

Use the root `Makefile`:

- `make install-dev`: install Python dev dependencies.
- `make run`: start the TUI.
- `make lint`: run Ruff.
- `make test`: run pytest.
- `make tui-smoke`: check TUI launcher help.
- `make verify`: run lint, tests, script checks, and TUI smoke checks.
- `make migrate` / `make migration-status`: apply or inspect migrations.

## Coding Style & Naming Conventions

CI uses Python `3.13`; Ruff targets `py310` syntax with 100-character lines, double quotes, space indentation, and import sorting. Keep modules small and explicit, especially around authorization, persistence, and command execution. Tests and Python modules use `snake_case`. Avoid cross-layer shortcuts or duplicated business rules.

## Testing Guidelines

Pytest discovers `test_*.py`, `Test*` classes, and `test_*` functions under `tests/`. Use markers (`unit`, `integration`, `slow`, `e2e`) when useful. Add or update tests for TUI launcher contracts, migrations, authorization, telemetry, and persistence. Run focused tests such as `./venv/bin/pytest -q tests/unit/test_memory.py`.

## Commit & Pull Request Guidelines

Recent history uses prefixes such as `feat:`, `docs:`, and `chore:`; follow that pattern with concise, imperative summaries. Pull requests should state the problem, approach, validation performed, and documentation updates.

## Security & Configuration Tips

Start from `.env.example` and keep secrets out of commits. Treat local databases, logs, and runtime artifacts as disposable developer state. This project provides constrained local command execution, not a hardened sandbox; keep authorization changes conservative, project-aware, auditable, tested, and documented.
