# Product Vision

## Positioning

DevSynapse AI is a conversational desktop assistant for GitHub, GitHub Actions
and repository work.

It gives people a clear, approachable way to understand and operate projects
without requiring them to master terminal commands, GitHub's fragmented
screens or workflow YAML before they can be productive.

DevSynapse does not merely wrap GitHub buttons in chat. It builds a current
model of the user's projects, explains what is happening, maintains context
across conversations and safely performs approved work through Git and GitHub.

## Product Promise

The user should be able to open one installed application and ask:

> What is happening in my projects, what needs attention and can you help me
> resolve it?

DevSynapse should respond as a knowledgeable collaborator: converse naturally,
show relevant evidence, adjust its explanation to the user and carry out
reviewable actions.

## Primary Users

### New and learning developers

They need Git and GitHub concepts explained without being forced into CLI
syntax. The application should teach through the real project in front of them,
not through detached tutorials.

### Working developers

They understand repositories but lose time navigating branches, pull requests,
checks, Actions runs, permissions and release processes. DevSynapse should
reduce that operational load without hiding consequential changes.

### Experienced maintainers

They need fast portfolio awareness, precise diagnostics and automation across
several repositories. DevSynapse should become concise and powerful when the
user demonstrates or explicitly requests that level.

## Canonical Experience

DevSynapse is installed as a normal desktop application and launched from the
operating system. A normal user does not need:

- a terminal;
- Python, Node.js or Rust installed;
- the DevSynapse source checkout;
- the GitHub CLI;
- knowledge of slash commands;
- manual editing of environment files.

The application packages its runtime, manages updates and guides authentication
through visual flows.

## Conversation as the Interface

Conversation is the primary interaction model. DevSynapse should feel willing
to talk, not like a command launcher that adds polite text.

It should:

- greet and orient a new user without overwhelming them;
- ask one focused question when a choice materially changes the outcome;
- explain unfamiliar GitHub terms in context;
- connect current questions with earlier project decisions;
- offer a recommendation and the reasoning behind it;
- present evidence, previews and progress as visual conversation elements;
- confirm consequential actions in plain language;
- become brief when the user prefers speed;
- become more explanatory when the user is learning or asks why.

The user can explicitly choose conversation preferences such as experience
level, detail, tone and proactive guidance. Inferred preferences are visible,
editable and resettable.

## Core Capabilities

### Project connection and portfolio

- connect GitHub accounts through a guided flow;
- discover or add local repositories without requiring terminal commands;
- associate local repositories with GitHub repositories safely;
- show which projects require attention and why;
- preserve project purpose, conventions and recent decisions.

### Git and commit assistance

- explain local changes;
- distinguish staged, unstaged and untracked work;
- propose coherent commit groups and messages;
- guide branches and synchronization;
- prepare and create approved commits;
- prevent accidental cross-project or stale operations.

### Pull request assistance

- explain branch readiness and missing checks;
- prepare pull request titles, descriptions and reviewer context;
- show the exact base, head and repository;
- create approved pull requests;
- summarize review feedback and unresolved conversations;
- guide safe follow-up work without merging automatically.

### GitHub Actions mastery

- discover and explain workflows, triggers, permissions, jobs and dependencies;
- validate workflow structure and identify risky permissions;
- create or modify workflows through guided, previewed changes;
- monitor runs, jobs, checks and annotations;
- retrieve and summarize failure logs;
- distinguish code, environment, permission, secret, dependency and transient
  failures;
- recommend a recovery path and execute approved reruns or dispatches;
- explain secrets and environments without exposing secret values;
- connect pull request status with the workflows that gate it.

### Releases and recurring operations

- prepare changelogs and release notes from repository evidence;
- verify tags, branches, checks and artifacts;
- publish releases only after an explicit preview and confirmation;
- turn repeated, approved repository processes into visible procedures.

## Product Principles

### GitHub expertise is core

GitHub and GitHub Actions are not add-ons. Their concepts, failure modes and
safety constraints belong in the domain model, interface and test strategy.

### Dialogue before commands

The user expresses intent in ordinary language. DevSynapse translates intent
into typed operations and explains the result. It does not teach users to
operate the product through hidden command syntax.

### Evidence before advice

Recommendations reference current repository, pull request or workflow state.
Observed facts, inferences and suggestions are distinguishable.

### Preview before consequence

Commits, pushes, workflow edits, dispatches, pull requests and releases show the
project, account, repository, target and expected effects before execution.

### Progressive disclosure

New users see clear language and the next relevant choice. Experienced users
can expand technical details, logs, payloads and advanced controls.

### Adaptation with user control

Explicit preferences win. Learned preferences carry evidence and confidence,
can expire, and can be corrected or removed by the user.

### Packaged and dependable

Installation, authentication, updates, credential storage and recovery are part
of the product. They cannot require a development environment.

## Action Risk Classes

| Class | Examples | Default behavior |
|---|---|---|
| Observe | repository status, PR checks, Actions runs and logs | automatic |
| Prepare | commit groups, PR drafts, workflow patches, release notes | automatic, no mutation |
| Local mutation | stage, branch, workflow edit, commit | visual preview and confirmation |
| Remote mutation | push, create PR, dispatch/rerun Action, publish release | visual preview and confirmation |
| Destructive | force push, reset, deletion, merge override | unavailable by default |

Risk is defined by the operation registry, not by the model's wording.

## Deliberate Non-Goals

DevSynapse is not:

- a general-purpose coding agent;
- an IDE or source-code editor;
- a terminal frontend;
- a generic shell assistant;
- a GitHub analytics dashboard;
- a multi-user administration platform;
- a model/provider control panel;
- an autonomous merge or deployment authority;
- a plugin or multi-agent construction kit.

## Success Measures

- a new user connects GitHub and understands their first project without using
  a terminal;
- users can explain why a workflow failed after interacting with DevSynapse;
- accepted commit and pull request proposals require minimal correction;
- consequential actions always retain project, repository and target context;
- conversation detail and terminology match explicit user preferences;
- recurring GitHub procedures complete with fewer context switches;
- no credentials, cross-project mutations or stale approvals are leaked or
  executed.

## Current Transition

The current v1 implementation is a Python/Textual TUI with a generic command
bridge. The repository history contains a previous Tauri/React desktop
application and packaged backend.

The target will selectively recover that desktop foundation while retaining
useful current core services. The TUI, slash commands and shell installer are
legacy migration tools, not the future end-user experience. Planned desktop and
GitHub capabilities must not be advertised as shipped until their roadmap
acceptance criteria pass.
