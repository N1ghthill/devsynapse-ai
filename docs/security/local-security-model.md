# Desktop and GitHub Security Model

## Scope

DevSynapse is a single-user desktop application that operates local
repositories and an authenticated GitHub account. It runs with the user's OS
permissions and communicates with GitHub and configured LLM providers.

It is not a sandbox for malicious repositories. Its primary security goals are:

- protect GitHub and provider credentials;
- prevent unintended local or remote mutations;
- prevent cross-project and wrong-repository operations;
- ensure approvals refer to current state;
- keep secret values out of prompts, logs, memory and frontend payloads;
- make consequential behavior visible to users at different experience levels.

## Current Transitional Risk

The current v1 TUI contains a generic command bridge and broad Build-mode
autoexecution. It runs on the host with the user's permissions and is not the
target security model.

During migration:

- do not add new product workflows to the generic bridge;
- keep the TUI out of target end-user packaging;
- use the bridge only in trusted development environments;
- treat `shell=False` and blacklists as limited mitigations, not a security
  boundary.

## Desktop Process Boundary

The packaged application starts a bundled backend sidecar. The frontend may
communicate only with that instance.

Required controls:

- signed or bundle-verified sidecar path;
- private typed IPC;
- per-launch authentication if loopback transport is used;
- strict origin restrictions;
- no generic command endpoint;
- process cleanup on exit;
- redacted user-scoped logs;
- version compatibility check between desktop and backend.

The backend is not exposed as a public or LAN service.

## Credential Boundary

GitHub and provider credentials are handled by the backend and platform secure
storage. React receives only non-secret account and capability metadata.

Credentials must never appear in:

- LLM prompts or tool payloads;
- conversation or learned preference records;
- operation audit JSON;
- logs and crash reports;
- repository remote URLs shown to the user;
- frontend state, browser storage or rendered error details.

GitHub secret values are not retrieved. The application may inspect names,
references and missing-configuration signals allowed by GitHub without
displaying values.

## GitHub Authentication

First-run authentication uses a guided browser or device flow. Manual token
entry is an advanced fallback.

The application:

- displays the active account;
- explains requested capabilities in user-appropriate language;
- requests the minimum practical access;
- detects expired, revoked or insufficient credentials;
- supports disconnect and credential removal;
- never treats a successful provider login as GitHub authorization.

## Operation Policy

Registered operations have deterministic risk:

| Risk | Policy |
|---|---|
| Observe | automatic |
| Prepare | automatic without mutation |
| Local mutation | current preview and explicit confirmation |
| Remote mutation | account/repository/target preview and explicit confirmation |
| Destructive | unavailable by default |

The model cannot alter risk, approve an operation or select a broader
credential.

## Preview Integrity

An approval applies to one immutable preview. Execution fails closed when:

- local repository state changed;
- account, owner or repository changed;
- branch, pull request, workflow, run or release target changed;
- credential capabilities changed;
- the preview expired;
- submitted inputs differ from approved inputs.

A new state produces a new preview and explanation.

## Project and Repository Identity

Local identity:

```text
canonical project id
canonical root
Git directory/worktree identity
HEAD and state fingerprint
```

Remote identity:

```text
GitHub account
owner
repository
remote
branch/ref/object id
```

The UI presents these before consequential operations. Friendly repository
names never replace canonical identifiers in policy checks.

## GitHub Actions Safety

Workflow operations additionally enforce:

- exact workflow identity and ref;
- declared dispatch input validation;
- permissions review for workflow changes;
- protected environment awareness;
- no secret-value retrieval or echoing;
- log and artifact size limits;
- cancellation and rerun idempotency;
- confirmation before dispatch, rerun or cancellation.

Failure diagnosis separates evidence from inference and includes confidence.
The assistant cannot invent a missing secret value or bypass a protected gate.

## Conversational Adaptation Boundary

The assistant may adapt tone, terminology, depth and proactive guidance.
It may not adapt:

- risk classification;
- confirmation requirements;
- credential scope;
- project isolation;
- evidence standards;
- destructive-operation availability.

Explicit preferences override learned preferences. Learned values are visible,
correctable and removable.

## Audit

Consequential operations record:

- account, project and repository identity;
- operation, preview and approval identifiers;
- current-state fingerprint;
- user decision;
- start and completion timestamps;
- normalized result and GitHub object identifiers;
- redacted recovery details.

Audit records avoid full file content, raw workflow logs, tokens and secret
values.

## Release Security

Desktop releases require:

- reproducible dependency locks;
- signed artifacts where supported;
- updater signature verification;
- bundled-backend integrity checks;
- clean-machine install and uninstall tests;
- dependency and GitHub API compatibility monitoring;
- migration rollback or recovery guidance.

## Escalation Conditions

Additional isolation is required before supporting:

- shared OS accounts or multiple application users;
- organization-wide unattended automation;
- untrusted repository execution;
- automatic merge or deployment;
- remote control of the desktop application;
- enterprise credential brokering.
