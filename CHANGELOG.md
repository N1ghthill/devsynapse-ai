# Changelog

All notable changes to this project should be documented in this file.

The format follows a simple Keep a Changelog style and uses human-readable release notes.

## [Unreleased]

### Added
- MIT license and open source contribution policy
- structured documentation set for contributors and maintainers
- conversation management with rename, delete and sidebar navigation
- persisted execution status and conversation rehydration
- token and cost telemetry for chat responses
- dashboard-level LLM usage reporting and cost views
- CSV export for usage history
- project-aware mutation authorization and admin audit flow

### Changed
- command extraction and repair logic for assistant responses
- session handling through stable JWT configuration
- chat UX for command proposal, execution and blocked/failure states
- cost attribution now prefers explicit persisted project context where available

### Fixed
- multiple issues around command parsing, command selection and false success claims
- backend timeout behavior when provider latency is high
- login/session invalidation after API restarts

## [2026-04-24]

### Verified
- backend tests: `106 passed`
- frontend production build: passed

This date reflects the current documented repository baseline rather than a formal packaged release.
