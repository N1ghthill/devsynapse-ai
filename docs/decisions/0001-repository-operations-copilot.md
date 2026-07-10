# ADR 0001: Reposition DevSynapse as a Repository Operations Copilot

- Status: accepted, superseded in part by ADR 0002
- Date: 2026-07-08

## Context

DevSynapse v1 is described as a local coding agent and gives the model access
to a generic command bridge. The implemented TUI, project registry, memory,
telemetry and local execution capabilities are useful, but the broad
coding-agent framing does not identify a distinctive operator problem.

The intended product is a conversational assistant for organizing projects and
automating repository processes such as commits, branches, GitHub Actions,
pull requests and releases.

## Decision

DevSynapse will become a local-first repository operations copilot.

This decision originally retained the Textual TUI as canonical and treated
GitHub as optional. ADR 0002 supersedes those interface and integration
choices: the canonical target is a packaged desktop application and GitHub is a
core product boundary. The typed operation and repository-safety decisions
remain active.

Generic shell execution will no longer be the primary tool mechanism. It may
remain as an advanced operator feature, isolated from normal model-driven
automation.

## Consequences

Positive consequences:

- the product has a narrower and more defensible purpose;
- repository operations can use domain-specific validation and previews;
- the UI can organize work around projects, changes and automation;
- safety decisions no longer depend on shell-string pattern matching;
- memories and recipes can represent operational conventions directly.

Costs and tradeoffs:

- the tool layer and authorization model require substantial refactoring;
- GitHub integration introduces credentials, network failures and rate limits;
- current prompts, command extraction and parts of the agent loop become
  transitional;
- documentation must distinguish current capabilities from target behavior;
- remote operations need stronger integration and contract tests.

## Alternatives Considered

### Continue as a general coding agent

Rejected because the scope is broad, the market is crowded and unrestricted
tool execution conflicts with the desired safety and organization experience.

### Build a non-conversational Git dashboard

Rejected because conversation is useful for recovering context, explaining
state and translating operator intent into a reviewable plan.

### Make GitHub the primary product domain

Originally rejected. ADR 0002 reverses this decision after product
clarification. Local repositories remain important, but GitHub and GitHub
Actions now define the product's central expertise.

## Follow-up

Implementation is governed by [the repository operations
roadmap](../roadmap.md) and [the target
architecture](../architecture/repository-operations.md).

See also [ADR 0002](0002-packaged-desktop-github-first.md).
