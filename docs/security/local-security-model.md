# Local Security Model

DevSynapse AI is a local-first terminal coding agent. It is meant to run on a
developer machine with the user's own LLM provider API key. It is not a public
SaaS, a hardened sandbox or a multi-tenant service.

## Security Goal

The main goal is to reduce local development risk while keeping the agent useful:

- keep provider API keys in runtime configuration or environment variables, not
  in source control;
- validate command format before execution;
- restrict command families to `bash`, `read`, `glob`, `grep`, `edit` and
  `write`;
- block configured high-risk command patterns;
- require project scope for project-bound mutations;
- keep project-scoped mutating commands inside the registered project root;
- record command outcomes, status and reason codes in SQLite;
- block `sudo` from chat-driven command execution.

## Command Boundary

DevSynapse exposes a constrained command bridge, not a raw unrestricted shell.
The bridge parses model tool calls, checks the command family, applies command
allowlists and resolves project working directories before execution.

TUI sessions are treated as trusted local-operator sessions. Trusted tool calls
may execute supported tools, including `edit` and `write`, and trusted `bash`
can use shell syntax. This is still not a sandbox boundary: commands run on the
host machine with the current user's privileges.

Commands containing `sudo` are blocked before execution with
`privileged_setup_required`. Privileged OS setup must happen manually in a real
terminal. Unexpected failures that require an interactive `sudo` password or TTY
are classified with `interactive_sudo_required`.

When a conversation is scoped to a registered project, that project is the
mutation boundary. Write/edit and mutating bash actions that point outside it are
blocked with `project_scope_mismatch`. Read-oriented commands can still inspect
allowed paths so the agent can gather context.

LLMs sometimes produce placeholder paths such as `/home/user/projects`,
`~/projects` or `/workspace`. Before validation and execution, the command
bridge normalizes those placeholders to configured local repository/workspace
roots. If the command then points at a different project than the active one, a
mutating command is blocked instead of silently switching scope.

## Runtime Secrets

Runtime config defaults to `~/.config/devsynapse-ai/.env`. Set one or more of:

- `DEEPSEEK_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENCODE_ZEN_API_KEY`
- `OPENCODE_GO_API_KEY`

The repository `.env.example` is safe to commit because keys are blank. Do not
commit populated runtime config files, SQLite databases or logs.

## Non-Goals

This project does not provide:

- kernel-level sandbox isolation;
- safe execution of arbitrary untrusted code;
- public internet hardening;
- multi-tenant isolation;
- formal secrets rotation or incident-response workflows.

## Local Operator Checklist

Before normal use:

- configure provider API keys only in runtime config or environment variables;
- keep local databases and logs out of commits;
- register only project directories you trust;
- review proposed commands before allowing mutations;
- use disposable `DEVSYNAPSE_HOME` directories for experiments;
- treat command execution as host execution by your current user.

## When to Add More Hardening

Add stronger isolation if the product direction changes toward shared machines,
remote access, untrusted users or untrusted repositories. In those cases, prefer
OS-level isolation, a dedicated system user, container boundaries, stricter
network policy and external secret handling.
