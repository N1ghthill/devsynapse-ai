# Security Policy

## Security Posture

DevSynapse AI includes controlled command execution, authentication and project-scoped mutation permissions. That improves the baseline significantly over an unrestricted local assistant, but it should not be described as full sandbox isolation or production-complete hardening.

Current security-related controls include:
- JWT-based authentication
- first-run setup for admin password, DeepSeek API key and repository workspace
- persisted users and password hashing
- route protection for sensitive operations
- command validation and command allowlists
- role-aware authorization
- project-scoped write permissions for non-admin users
- trusted local-operator execution for admin users
- administrative audit logs

## Known Boundaries

The following are important limits of the current system:
- command execution is constrained, but not a kernel-level sandbox
- RBAC is intentionally simple
- SQLite is appropriate for local and early-stage use, not a full multi-tenant production architecture
- secrets rotation and formal incident-response workflows are not yet fully developed

## Reporting Vulnerabilities

If you find a security issue, do not open a public issue with exploit details.

Instead, share:
- affected component
- reproduction steps
- impact assessment
- suggested mitigation if available

Use a private communication channel controlled by the maintainers when possible.

## Safe Disclosure Guidance

When discussing security in PRs or issues:
- avoid posting live secrets
- avoid posting exploit payloads that materially increase risk before a fix exists
- prefer minimal reproductions
- clearly distinguish confirmed issues from hardening suggestions

## Dependency Monitoring

Dependabot watches GitHub Actions, Python, frontend npm and Tauri Cargo manifests weekly.
Python and npm dependency audits should remain clean before release. Rust/Tauri advisories
can include transitive desktop stack warnings that are not directly pinned by this project;
triage those through `frontend/src-tauri/Cargo.lock` and prefer upstream Tauri updates when
patched versions are blocked by the current Tauri dependency graph.

## Operational Advice

For local deployments:
- replace default seeded passwords
- complete the first-run setup when prompted
- keep `.env` out of version control
- keep the API bound to localhost unless network access is intentional
- keep CORS restricted to local or explicitly trusted browser origins
- limit who can access the machine running the assistant
- use admin accounts only when unrestricted local agent execution is intended
- review mutation permissions before enabling write access for users

## Documentation References

- architecture: [docs/architecture/overview.md](docs/architecture/overview.md)
- API overview: [docs/api/overview.md](docs/api/overview.md)
- runtime notes: [docs/deployment/runtime.md](docs/deployment/runtime.md)
- local security model: [docs/security/local-security-model.md](docs/security/local-security-model.md)
