# DevSynapse AI Evaluation Evidence

This directory contains product evaluation artifacts generated from disposable
test projects.

## 2026-05-02 Appraisal

- Full appraisal: [2026-05-02-appraisal.md](2026-05-02-appraisal.md)
- API and execution evidence: [2026-05-02-api-execution-results.json](2026-05-02-api-execution-results.json)
- Screenshots: [screenshots/](screenshots/)

This first pass validated the local orchestrator, project scoping, command
authorization, UI smoke flow and telemetry without requiring a real LLM call.

## 2026-05-02 Real DeepSeek Run

- Evidence report: [real-llm/2026-05-02-real-deepseek-evidence.md](real-llm/2026-05-02-real-deepseek-evidence.md)
- Structured result: [real-llm/2026-05-02-real-deepseek-agent-result.json](real-llm/2026-05-02-real-deepseek-agent-result.json)
- Screenshots: [real-llm/screenshots/](real-llm/screenshots/)
- Reproducible benchmark plan: [reproducible-benchmarks.md](reproducible-benchmarks.md)

This pass used the configured DeepSeek API key on a disposable Python project
with intentionally failing tests. DevSynapse diagnosed the bug, edited the code
and finished with `3 passed in 0.01s`.

## Reproducible Agent Evaluation

The repository now includes a disposable evaluation harness:

```bash
make eval-agent
```

The target creates a fresh project under `/tmp/devsynapse-agent-evaluations/`,
runs baseline tests, verifies command policy behavior and writes Markdown/JSON
reports. When a DeepSeek API key is available, it also runs a real agent turn
against the disposable project. To validate only the harness and policy checks:

```bash
make eval-agent EVAL_AGENT_ARGS=--no-llm
```

## Safety Notes

- No GitHub push was performed.
- Disposable project paths were under `/tmp`.
- Private issue notes are kept outside the repository under
  `~/Documentos/devsynapse-private-evaluation-2026-05-02/`.
