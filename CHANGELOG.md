# Changelog

All notable changes to this project should be documented in this file.

The format follows a simple Keep a Changelog style and uses human-readable release notes.

## [Unreleased]

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
