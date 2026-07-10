# Scope Reduction and Legacy Retirement

## Purpose

Reduce DevSynapse to the components required for a packaged conversational
GitHub copilot while keeping `main` usable during migration.

Removal follows replacement. A legacy component is deleted after its target
capability works in the packaged desktop application and its data or developer
workflow has a documented migration.

## Retain

Retain and evolve:

- conversation persistence;
- project registry and path resolution;
- explicit user preferences;
- project and procedural memory;
- provider transport needed for conversation;
- SQLite migrations and audit foundations;
- correlation identifiers;
- usage safeguards required for reliability;
- current test fixtures that validate retained backend behavior.

## Refactor

Refactor behind target boundaries:

| Current area | Target |
|---|---|
| `core/brain.py` | conversation orchestration using typed operations |
| `core/prompts.py` | GitHub collaborator prompt with adaptive dialogue |
| project resolver | canonical local and GitHub repository identity |
| agent runs | operation proposals, progress and audit |
| user preferences | explicit/confirmed/session conversation profile |
| provider routing | internal reliability concern, not primary UI |
| telemetry | private diagnostics and safeguards, not a product dashboard |
| historical frontend | minimal desktop shell and reusable primitives |

## Retire After Replacement

| Legacy area | Removal gate |
|---|---|
| `devsynapse/tui.py`, screens and TCSS | desktop covers setup, conversation, projects, activity and settings |
| slash commands and command palette | equivalent visual/conversational flows exist |
| shell install/update/uninstall wrappers | packaged install, update and uninstall are stable |
| `OpenCodeBridge` model access | typed Git/GitHub operations cover product workflows |
| command extraction and repair | providers use validated operation calls |
| coding builder/planner/checklist behavior | GitHub task planning and operation progress replace it |
| TUI appearance preferences | desktop preference migration exists |
| TUI-only tests | desktop tests cover retained contracts |

## Do Not Promote to Product Surface

Keep internal or remove if unused:

- model catalog selection;
- token/cost dashboards;
- plugin administration;
- global skill management;
- multi-agent configuration;
- generic shell tools;
- multi-user roles and admin controls;
- low-level SQLite or provider diagnostics.

An advanced diagnostics panel may expose support information, but these areas
do not receive primary navigation or onboarding prominence.

## Persistence Review

Existing tables require classification before desktop v1:

- keep and migrate: conversations, projects, user preferences;
- reshape: agent runs, procedural memories, audit logs;
- internal-only: model catalog and LLM telemetry;
- review for removal: users, admin roles and project-permission concepts that
  only served the previous multi-user product.

Do not drop tables until a migration demonstrates that no supported current
data is lost unexpectedly.

## Historical Frontend Recovery

Recover from history:

- Tauri packaging and updater structure;
- sidecar lifecycle patterns;
- icons;
- React build configuration;
- useful chat streaming and error-boundary components;
- desktop CI and smoke-test ideas.

Do not restore:

- login/JWT;
- admin;
- role permission management;
- generic dashboard;
- provider monitoring;
- former route tree and CSS wholesale.

## Completion Criteria

Scope reduction is complete when:

- release artifacts contain no Textual runtime;
- end-user docs contain no terminal setup;
- the model has no generic shell tool;
- the desktop has only Conversation, Projects, Activity and Settings;
- GitHub and Actions workflows use typed operations;
- internal model/provider complexity is absent from normal navigation;
- unused multi-user, coding-agent and plugin product concepts are removed from
  code, migrations or retained only behind documented compatibility needs.
