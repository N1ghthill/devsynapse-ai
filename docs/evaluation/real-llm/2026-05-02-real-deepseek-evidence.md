# Real DeepSeek Agent Evidence - 2026-05-02

## Goal

Validate DevSynapse AI with the configured DeepSeek API key on a disposable project,
collecting public evidence suitable for product review.

No real user repository was used as the target project. The test fixture lived under:

```text
/tmp/devsynapse-real-llm-eval-2026-05-02/repos/tiny-ledger-lab
```

## Evidence Artifacts

- Structured result: [2026-05-02-real-deepseek-agent-result.json](2026-05-02-real-deepseek-agent-result.json)
- Chat result screenshot: [screenshots/2026-05-02-real-deepseek-chat-result.png](screenshots/2026-05-02-real-deepseek-chat-result.png)
- Project lock screenshot: [screenshots/2026-05-02-real-deepseek-project-selector.png](screenshots/2026-05-02-real-deepseek-project-selector.png)
- DeepSeek configured screenshot: [screenshots/2026-05-02-real-deepseek-settings-configured.png](screenshots/2026-05-02-real-deepseek-settings-configured.png)

## Test Fixture

The disposable project was a tiny Python package with invoice/discount logic.
The baseline intentionally failed:

```text
2 failed, 1 passed
```

The bug was in `apply_discount`, which added the discount instead of subtracting it.

## Agentic Flow

The request asked DevSynapse to:

1. inspect the active project;
2. run the tests;
3. diagnose the failing tests;
4. edit the code;
5. run the tests again;
6. return a short final summary.

DevSynapse used DeepSeek with tool execution enabled and project context locked to
`tiny-ledger-lab`.

## Result

DevSynapse fixed the implementation:

```diff
-    return round(total + (total * percent / 100), 2)
+    return round(total - (total * percent / 100), 2)
```

Final validation:

```text
3 passed in 0.01s
```

Usage recorded by the app for this project turn:

```text
provider: deepseek
model: deepseek-v4-flash
total_tokens: 29840
prompt_cache_hit_tokens: 23680
prompt_cache_miss_tokens: 4656
reasoning_tokens: 414
estimated_cost_usd: 0.001736
```

## Product Signals Confirmed

- DeepSeek API key configured and working.
- Conversation project lock worked with `tiny-ledger-lab`.
- The orchestrator inspected files, edited code and validated the result.
- Token and cost telemetry were attached to the chat turn.
- The UI displayed the final command output and project attribution.

## Private Follow-Up

Any operational issue observed during this run was documented outside the public
repository. Those notes are intentionally not part of this public evidence set.
