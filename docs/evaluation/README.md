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

This pass used the configured DeepSeek API key on a disposable Python project
with intentionally failing tests. DevSynapse diagnosed the bug, edited the code
and finished with `3 passed in 0.01s`.

## Safety Notes

- No GitHub push was performed.
- Disposable project paths were under `/tmp`.
- Private issue notes are kept outside the repository under
  `~/Documentos/devsynapse-private-evaluation-2026-05-02/`.
