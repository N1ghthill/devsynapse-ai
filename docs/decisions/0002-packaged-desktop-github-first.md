# ADR 0002: Packaged Desktop and GitHub-First Product

- Status: accepted
- Date: 2026-07-08
- Supersedes: the TUI-first and GitHub-optional parts of ADR 0001

## Context

ADR 0001 narrowed DevSynapse from a general coding agent to a repository
operations assistant, but it retained the Textual TUI as the canonical interface
and treated GitHub as optional. That still assumes terminal familiarity and
understates the product's main differentiation.

The intended user includes people who are new to programming and developers
who understand code but find GitHub, Git workflows and GitHub Actions difficult
to operate confidently. DevSynapse should hide incidental CLI complexity while
teaching concepts through conversation and reviewable visual flows.

The repository history already contains a Tauri 2, React and TypeScript desktop
application with bundled-backend support and Windows/Linux packaging. It was
removed when the TUI became canonical, so the desktop direction has prior
implementation evidence.

## Decision

DevSynapse will be distributed as a packaged desktop application. Normal users
must not need a terminal, Python environment, `gh` CLI or repository checkout
to install, configure or operate it.

GitHub and GitHub Actions are core product capabilities rather than peripheral
integrations. The application should use typed GitHub operations and direct API
integration behind a conversational, visual interface.

The target desktop stack is Tauri 2 with React and TypeScript, reusing selected
historical assets and contracts where they remain appropriate. The Python core
may initially run as a bundled sidecar while domain boundaries are stabilized.

The Textual TUI becomes a transitional development and migration surface. It is
not part of the target end-user product.

## Conversation Decision

Conversation is the primary interaction model, not a command prompt embedded
in a window. DevSynapse should:

- maintain a natural dialogue;
- explain GitHub concepts in language appropriate to the user;
- ask focused questions when intent, risk or target is unclear;
- adapt detail, terminology and pace from explicit preferences and confirmed
  learning;
- show visual evidence and previews inside the conversation;
- avoid terse command-only behavior unless the user prefers it.

Explicit preferences override inferred preferences. Users can inspect, edit
and reset what the assistant has learned.

## Scope Reduction

The target product does not expose:

- a TUI or slash-command interface;
- a generic shell console;
- provider routing, token telemetry or model selection as primary navigation;
- admin, multi-user or role-management screens;
- plugin, skill or multi-agent configuration as end-user concepts;
- a general-purpose code editor or coding-agent mode.

Internal provider, memory and extension mechanisms may remain when they serve
the product, but they do not define its interface.

## Consequences

Positive:

- installation and operation become approachable to non-terminal users;
- the interface can combine dialogue, evidence, previews and guided actions;
- GitHub expertise becomes the clear differentiator;
- prior Tauri packaging work can reduce delivery risk;
- the backend can keep deterministic repository and authorization logic.

Costs:

- desktop packaging and update flows return as product-critical concerns;
- the legacy TUI and installer need an explicit retirement plan;
- GitHub authentication, API compatibility, rate limits and credential storage
  become core engineering responsibilities;
- historical desktop code cannot be restored wholesale because its login,
  admin and generic dashboard surfaces conflict with the simplified product.

## Follow-up

The active roadmap and architecture documents must treat:

- packaged desktop distribution as canonical;
- GitHub connection as first-run product setup;
- TUI and shell workflows as transitional;
- adaptive dialogue as a product capability with explicit acceptance tests;
- historical frontend code as a source for selective recovery, not automatic
  restoration.
