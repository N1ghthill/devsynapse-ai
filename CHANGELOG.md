# Changelog

## Unreleased

## 1.2.9 - 2026-07-13

### Desktop

- Refined the desktop layout with DevSynapse and Ruas.dev visual assets.
- Removed risky Copilot wording from product copy and package metadata.
- Added distribution-aware update messaging so Debian package installs use APT
  or a newer `.deb` instead of the AppImage updater path.
- Added in-app APT setup commands for Debian package installs.
- Added a copy button for Debian/Ubuntu APT setup commands.
- Added structured Git evidence and stale-state validation for commit previews.

### Release

- Added GitHub Pages deployment for the generated APT repository.
- Fixed release workflow authentication for publishing the APT repository.
- Normalized APT package filenames to Debian-style names without spaces.
- Added test coverage for APT repository package filename normalization.
- Added a manual APT upgrade smoke workflow.
- Documented APT setup, manual `.deb` upgrades and updater verification.
- Refreshed compatible Rust lockfile dependencies.

### Product direction

- Repositioned DevSynapse as a packaged conversational desktop assistant for
  GitHub, GitHub Actions and repository work.
- Made GitHub expertise and adaptive dialogue core product capabilities.
- Defined Tauri 2 + React/TypeScript with a bundled Python backend as the
  desktop transition architecture.
- Marked the Textual TUI, slash commands, shell installer and generic command
  bridge as transitional developer surfaces.
- Documented the target typed-operation, preview, approval and audit model.
- Added an incremental roadmap from packaged desktop foundation through
  GitHub connection, Actions diagnosis and confirmed operations.
- Marked the v1 generic command bridge and broad Build-mode execution as
  transitional.
- Documented selective recovery of the historical Tauri frontend without its
  former login, admin and generic dashboard surfaces.

## 1.0.0 - 2026-05-05

DevSynapse is now documented and packaged as a single TUI-first local coding
agent product.

### Product

- Official app command: `devsynapse`.
- Official maintenance commands: `update-devsynapse` and `uninstall-devsynapse`.
- Official build check: `devsynapse --version`.
- Operator work happens inside the TUI through slash commands.
- External operator subcommands remain unsupported by design.

### Install And Runtime

- `scripts/install.sh` supports `curl | bash` bootstrap installs.
- Installed commands are executable wrappers in `~/.local/bin`, not aliases.
- Previous DevSynapse shell aliases are removed during install and uninstall.
- Runtime config, data and logs stay outside the source checkout.
- Update refreshes dependencies, migrations and command wrappers.
- Uninstall removes wrappers and asks before deleting runtime data or config.

### TUI

- Added contextual slash-command suggestions.
- Added overlay help via `/help` and `Ctrl+H`.
- Added dynamic sidebar with session, model, telemetry and action panels.
- Added clearer status and notification handling.

### Cleanup

- Removed disconnected UI experiments and unused prototype files.
- Removed generated coverage/cache artifacts from source control.
- Documented the product contract in `docs/product-contract.md`.
