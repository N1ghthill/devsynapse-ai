# Reproducible Agent Benchmarks

This page defines the public, repeatable benchmark surface for DevSynapse AI.
The goal is evidence that can be regenerated without touching real user
repositories.

## Command

```bash
make eval-agent
```

Use this no-LLM variant for harness validation:

```bash
make eval-agent EVAL_AGENT_ARGS=--no-llm
```

Each run writes:

- `evaluation-report.md`: human-readable report with baseline test output,
  policy checks, optional LLM result, final test output and code diff.
- `evaluation-result.json`: structured output for later comparison or dashboard
  ingestion.

The default output root is `/tmp/devsynapse-agent-evaluations/`.

## Current Scenarios

### Tiny Ledger Lab

Purpose: validate whether DevSynapse can work inside a disposable Python
project, diagnose a failing test and produce a focused code edit.

Fixture:

- small Python package
- failing pytest suite
- intentionally wrong percentage-discount logic
- isolated git repository under `/tmp`

Evidence generated:

- baseline failing pytest output
- final pytest output
- git diff for the file edited by the agent
- LLM usage metadata when the DeepSeek step runs

### Project Boundary Checks

Purpose: prove that command execution remains project-aware while the agent is
working in a disposable repository.

Checks:

- `pwd_in_project`: confirms the command working directory resolves to the
  selected project.
- `blocked_path_escape`: verifies writes outside the selected project are
  blocked.
- `blocked_dangerous_pattern`: verifies dangerous shell patterns are blocked
  before execution.

### Telemetry Classification

Purpose: distinguish expected policy blocks from real operational failures in
monitoring.

Expected behavior:

- policy blocks are counted separately as `blocked`;
- operational command errors remain `failed`;
- dashboard health uses operational failures for warning/degraded status;
- informational policy-block alerts do not inflate active operational alerts.

## Publication Guidance

Public product material can cite successful generated reports, screenshots and
diffs from disposable projects. Reports that expose product defects should stay
outside the public repository until the defect is fixed and retested.

Do not publish:

- real user repository paths or source code;
- API keys or runtime config files;
- private failure notes;
- screenshots from unreleased or locally customized workflows unless they are
  explicitly marked as development evidence.

## Next Benchmarks

The next useful fixtures should cover:

- JavaScript/TypeScript test repair with `npm test`;
- documentation-only task with no file mutation;
- multi-file refactor with a narrow expected diff;
- missing dependency diagnosis where the correct action is to report the setup
  issue instead of editing source;
- budget-warning scenario that validates cost visibility during agent work.
