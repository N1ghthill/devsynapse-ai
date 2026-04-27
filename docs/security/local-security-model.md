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
- require admin authorization for global runtime settings updates
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
