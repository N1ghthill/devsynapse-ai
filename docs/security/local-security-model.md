# Local Security Model

DevSynapse AI is a local-first development assistant. It is meant to be downloaded,
run on a developer machine, and connected to the user's own DeepSeek API key. It is
not designed as a public SaaS or a hardened multi-tenant service.

## Security Goal

The main goal is to reduce local development risk while keeping the app useful:

- keep the DeepSeek API key in runtime configuration, not in source control
- bind the API to localhost by default
- restrict browser origins to local frontend origins by default
- require authentication for chat, settings, admin and command execution routes
- force first-run setup for admin password, DeepSeek API key and repository workspace
  when any of those runtime values are missing
- require admin authorization for global runtime settings updates
- require admin authorization for global saved knowledge writes
- require project mutation permission for non-admin project memory writes
- validate command format before execution
- restrict command types and non-admin bash commands through allowlists
- require explicit project scope for mutating commands
- require user/project permission for non-admin mutations
- keep mutating commands inside the registered project root
- save command outcomes, status and reason codes for auditability

## Command Boundary

DevSynapse exposes a constrained command bridge, not a raw shell. Supported command
families are `bash`, `read`, `glob`, `grep`, `edit` and `write`.

Read-oriented operations can inspect files and command output. Non-admin mutating
operations such as `edit`, `write`, `touch`, `mkdir`, `cp`, `mv`, `rm` and `chmod`
require confirmation and project-aware authorization. Non-admin users can mutate
only projects in their allowlist.

Admin users are treated as trusted local operators. Admin chat tool calls may
auto-execute supported OpenCode tools, including `edit` and `write`; admin `bash`
uses shell mode so pipelines, redirects and chained commands work as expected.
Admin file tools are not constrained to registered project roots or the normal
allowed-directory list. The bridge still rejects configured blacklist patterns and
records command telemetry, but this is not a sandbox boundary.

The chat UI can enable an "Aprovar tudo" fast path. This sends
`execute_command=true` on streaming chat turns so authorized tool calls run
without another confirmation click and emit audit events back to the chat. It
does not bypass backend role checks, project mutation allowlists, blacklist
checks, command telemetry or command execution records.

For admin users, "Aprovar tudo" is an operator mode rather than a project
allowlist mode. Supported OpenCode tools run directly, admin `bash` uses shell
syntax, and ordinary command failures are replayed to the model so it can keep
fixing and validating. When a conversation is scoped to a registered project,
that project remains the mutation boundary: write/edit and mutating bash actions
that point outside it are blocked with `project_scope_mismatch`. Read-only
reference commands can still inspect other allowed or registered repositories so
the agent can compare code and gather context without switching the working
project. Global admin sessions without a selected project remain trusted
local-operator sessions. To constrain what a person or agent can mutate more
narrowly, create a non-admin user and grant only the intended project allowlist.

LLMs sometimes produce placeholder filesystem paths such as `/home/user/projects`,
`~/projects` or `/workspace`. Before validation and execution, the command bridge
normalizes those placeholders to the configured local repository/workspace roots.
For example, `/home/user/projects/calculadora` maps to
`DEV_REPOS_ROOT/calculadora`. If a chat is already scoped to another project, a
normalized mutating command is blocked instead of silently switching projects.

Non-admin auto-execution is intentionally conservative. It is limited to low-risk
inspection through allowlisted bash commands. File-content tools such as `read`,
`grep` and `glob` are proposed for explicit confirmation instead of being sent to
the LLM automatically.

## Non-Goals

This project does not provide:

- kernel-level sandbox isolation
- safe execution of arbitrary untrusted code
- public internet hardening by default
- multi-tenant SaaS isolation
- formal secrets rotation or incident-response workflows

If the API is bound to `0.0.0.0` or another non-loopback host, DevSynapse logs a
warning because network exposure changes the risk profile. Use that only on trusted
networks and only when you understand that commands execute on the host machine.

## Local Operator Checklist

Before normal use:

- keep `API_HOST=127.0.0.1` unless network access is intentional
- keep `CORS_ALLOWED_ORIGINS` limited to known browser origins
- complete first-run setup before using the app normally
- configure `DEEPSEEK_API_KEY` only in runtime config or environment
- replace default local passwords
- use the admin role only when unrestricted local agent execution is intended
- keep global runtime settings changes limited to trusted admins
- register only project directories you trust
- grant mutation permissions only where writes are expected
- review proposed commands before confirming mutations
- treat local databases and logs as developer state that may contain project context

## When to Add More Hardening

Add stronger isolation only if the product direction changes. Examples include
shared machines, remote access, untrusted users, untrusted repositories or public
network exposure. In those cases, prefer OS-level isolation, a dedicated system
user, container boundaries, stricter network policy and external secret handling.
