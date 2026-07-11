# Testing Guide

The existing suite validates the current Python core and transitional TUI.
Desktop work extends this baseline with TypeScript, Rust, IPC, accessibility,
desktop smoke and clean-machine packaging tests.

## Current Verification Baseline

At the latest documentation refresh on `2026-07-11`, local verification produced:

- `870` passing Python tests;
- successful Ruff lint;
- successful frontend lint and production build;
- successful Tauri/Rust `cargo check`;
- successful shell script syntax checks, ShellCheck and Python script compilation;
- successful transitional TUI smoke;
- successful Tauri desktop window smoke.

## Test Layout

```text
tests/
├── unit/
└── integration/
```

### Unit Tests

Main areas covered:

- TUI launcher behavior;
- `brain` behavior and command extraction;
- `memory` persistence and telemetry;
- `opencode bridge` validation and authorization;
- plugin system basics;
- LLM routing and optimization helpers.

### Integration Tests

Main areas covered:

- end-to-end memory/brain/bridge interactions;
- installer and uninstaller script behavior;
- migration-backed persistence flows.

## Commands

Run all tests:

```bash
./venv/bin/pytest -q
```

Run focused modules:

```bash
./venv/bin/pytest -q tests/unit/test_cli.py
./venv/bin/pytest -q tests/unit/test_memory.py
./venv/bin/pytest -q tests/unit/test_brain.py
```

Run repository verification:

```bash
make verify
```

Run only the desktop shell smoke:

```bash
make desktop-smoke
```

`desktop-smoke` opens the Tauri application briefly and treats a healthy app
that remains alive until timeout as success. It runs when a graphical display
or `xvfb-run` is available and skips explicitly otherwise.

Script validation:

```bash
make script-check
```

`make script-check` always runs shell syntax checks and Python script
compilation. If `shellcheck` is installed locally, it also runs ShellCheck
against the shell entry points.

Linting:

```bash
make lint
```

Ruff checks application code and tests for import order and basic correctness.

Disposable agent evaluation:

```bash
make eval-agent
```

`make eval-agent` creates a timestamped benchmark run under
`/tmp/devsynapse-agent-evaluations/`, initializes a small Python project with
failing tests, validates project-scope policy blocks and, when a provider API key
is configured, asks DevSynapse to diagnose, edit and re-run the primary fixture.
Reports are written as Markdown and JSON inside the generated `reports/`
directory.

GitHub Actions runs the same local verification surface in a Python `3.13`
virtual environment:

```bash
make install-dev
make verify
make eval-agent EVAL_AGENT_ARGS=--no-llm
```

Release packaging is validated separately by the `Release Packages` workflow.
It runs on native Linux, Windows and macOS runners, builds the packaged Python
sidecar, emits Tauri bundles for each operating system, generates signed updater
artifacts when updater signing secrets are configured and packages the Linux
`.deb` output into an APT repository archive.

## Expectations For Contributors

Add or update tests when you change:

- desktop IPC and operation contracts;
- GitHub authentication, token storage and account status behavior;
- GitHub repository listing and local project to remote association behavior;
- project registration and native folder selection;
- Git evidence and preview fingerprints;
- TUI launcher and runtime configuration behavior;
- migration behavior;
- execution authorization;
- token/cost telemetry;
- conversation persistence semantics;
- provider routing or LLM transport contracts.

## Testing Philosophy

The repository currently emphasizes focused unit tests for logic-heavy services,
integration tests for persistence and command behavior, and script checks for
the installer/update operational surface.
