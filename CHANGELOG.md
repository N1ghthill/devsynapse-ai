# Changelog

All notable changes to this project should be documented in this file.

The format follows a simple Keep a Changelog style and uses human-readable release notes.

## [Unreleased]

### Added
- Native tool calling via DeepSeek's OpenAI-compatible tools API with strict function definitions, replacing regex-based command extraction as the primary mechanism.
- Thinking mode support with configurable reasoning_effort (high/max) and thinking toggle.
- Execution result interpretation loop: after command execution, the LLM receives the output and generates a natural-language explanation.
- `interpretation` field in `CommandExecutionResponse` and `CommandResult` frontend type.
- `DEEPSEEK_REASONING_EFFORT` and `DEEPSEEK_THINKING_ENABLED` environment variables.

### Changed
- Default model upgraded from `deepseek-chat` to `deepseek-v4-pro`.
- Base URL changed to `https://api.deepseek.com/beta` to enable strict function calling mode.
- System prompt rewritten in English with tool-aware instructions (removed legacy OpenCode DSL format).
- `temperature` parameter automatically omitted when thinking mode is enabled (API requirement).
- Default CORS origins are now limited to local frontend origins for local-first installs.

### Removed
- Command repair loop (`_needs_command_repair`, `_build_command_repair_messages`) — no longer needed with native tool calling.

### Fixed
- Tool-call conversion now preserves escaped quotes, backslashes, tabs and newlines in `edit`/`write` arguments before command execution.
- Auto-executed read-only tool calls now replay only the executed tool call back to the LLM, avoiding mismatched tool-call history when a model returns multiple tool calls.
- Read-only auto-execution now uses a conservative bash allowlist instead of treating every user-authorized bash command as safe to run without confirmation.
- API startup now warns when the backend is bound to a non-loopback host.

### Documentation
- Added a local security model and operator checklist for the downloaded, local-first DeepSeek API-key workflow.

## [v0.3.4] - 2026-04-25

### Added
- Non-interactive update flow through `scripts/update.sh`, `devsynapse update`, `update-devsynapse` and `make update`.
- Runtime backup before updates for existing config, SQLite databases and log file when present.

### Changed
- Installer now creates an `update-devsynapse` alias alongside `devsynapse` and `uninstall-devsynapse`.
- Launcher now supports `start`, `update`, `uninstall` and `help` subcommands.
- Shell and development launcher banners read the application version from `config/settings.py` instead of hardcoding it.
- CI and script checks now validate `scripts/update.sh`.

## [v0.3.3] - 2026-04-25

### Added
- Docker build now produces a FastAPI runtime image with the frontend production bundle included.
- `.dockerignore` keeps local runtime artifacts and dependency directories out of container build context.
- Per-user runtime config/data/log separation via XDG paths or `DEVSYNAPSE_HOME`.
- `scripts/ensure_runtime_config.py` for non-interactive runtime config bootstrap.
- Admin project listing and registration through `/admin/projects` and the Admin UI.

### Changed
- Installer, launcher and uninstaller now use the runtime config path instead of a repo-local `.env`.
- Installer now generates a strong JWT secret when the template/default value is unsafe and updates the configured admin user password.
- Chat, conversation, feedback and project routes now require authenticated users.
- Admin users now show global registered-project mutation scope instead of editable per-user allowlists.
- Public `/projects` responses hide local project paths; `/admin/projects` remains the path-bearing management surface.
- Production frontend builds default to same-origin API calls when `VITE_API_URL` is unset.
- `nginx.conf` is now an optional reverse-proxy baseline for the current FastAPI routes and SSE streaming endpoint.
- CORS origins are configurable through `CORS_ALLOWED_ORIGINS`; wildcard origins no longer enable credentialed CORS.

### Fixed
- Project-relative `read`, `edit` and `write` paths are normalized against the selected project before path validation.
- Mutating file and path-based bash commands must stay inside the resolved registered project.
- API request telemetry middleware now attaches background logging tasks to the actual response.
- Expected `/execute` command blocks or command failures no longer record false API 500 telemetry.

## [v0.3.2] - 2026-04-25

### Added
- CI browser smoke coverage for login, dashboard, settings save and admin navigation
- Dependabot configuration for GitHub Actions, Python and frontend dependencies
- Weekly Python lock-refresh workflow and local `make update-locks` command
- Tag-driven GitHub Release publishing workflow

### Fixed
- Launcher output no longer prints a custom admin password from `.env`
- Shell launcher shutdown now terminates backend and frontend process groups cleanly

## [v0.3.1] - 2026-04-25

### Added
- Scheduled and manually dispatchable CI runs
- CI checks for ShellCheck, shell syntax, Python utility script compilation and frontend ESLint
- Automated smoke tests for installer, uninstaller and development-server shutdown behavior
- Release notes for `v0.3.1`

### Changed
- `make verify` now runs backend lint, backend tests, script checks, frontend lint and frontend build
- GitHub Actions workflow now uses current `actions/checkout`, `actions/setup-python` and `actions/setup-node` major versions
- Runtime dependencies are kept in `requirements.txt`; development and test tooling stays in `requirements-dev.txt`
- Installer now prompts for the admin password during setup

### Fixed
- CI portability failures caused by tests depending on machine-specific absolute paths
- Project attribution now considers persisted project records in addition to configured projects
- `scripts/install.sh` now updates `.env` without corrupting values containing shell-sensitive characters
- `scripts/dev.py` now terminates backend/frontend process groups cleanly
- ShellCheck warnings in uninstall script

## [v0.3.0] - 2026-04-24

### Added
- MIT license and open source contribution policy
- structured documentation set for contributors and maintainers
- canonical development roadmap with current priorities, later work and deferred scope
- project attribution plan for execution, telemetry and dashboard alignment
- product showcase with use cases, screenshots and validation evidence
- conversation management with rename, delete and sidebar navigation
- persisted execution status and conversation rehydration
- token and cost telemetry for chat responses
- dashboard-level LLM usage reporting and cost views
- configurable LLM budget thresholds with dashboard/chat visibility and alert emission
- CSV export for usage history
- project-aware mutation authorization and admin audit flow

### Changed
- clarified DeepSeek-first positioning and removed provider-neutral/local-model language from strategic docs and settings
- chat contracts now accept, persist and return explicit project context
- aligned API and data model documentation with current route and migration surfaces
- command extraction and repair logic for assistant responses
- session handling through stable JWT configuration
- chat UX for command proposal, execution and blocked/failure states
- cost attribution now prefers explicit persisted project context where available

### Fixed
- `/execute` responses now preserve the resolved project name from command execution
- multiple issues around command parsing, command selection and false success claims
- backend timeout behavior when DeepSeek latency is high
- login/session invalidation after API restarts

## [2026-04-24]

### Verified
- backend tests: `116 passed`
- frontend production build: passed

This date reflects the current documented repository baseline rather than a formal packaged release.
