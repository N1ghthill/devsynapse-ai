# Changelog

## Unreleased

### Product direction

- Repositioned DevSynapse as a packaged conversational desktop copilot for
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
