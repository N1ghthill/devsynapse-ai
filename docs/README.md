# Documentation Index

This directory is the technical documentation entry point for the packaged
DevSynapse desktop product and its transitional Python/TUI implementation.

## Start Here

- repository overview: [../README.md](../README.md)
- product vision: [product-vision.md](product-vision.md)
- product contract: [product-contract.md](product-contract.md)
- implementation roadmap: [roadmap.md](roadmap.md)
- operator guide: [operator.md](operator.md)
- agent/contributor operating guide: [../AGENTS.md](../AGENTS.md)
- architecture overview: [architecture/overview.md](architecture/overview.md)
- target repository operations architecture:
  [architecture/repository-operations.md](architecture/repository-operations.md)
- persistence and data model: [architecture/data-model.md](architecture/data-model.md)

## Decisions

- [ADR 0001: repository operations
  copilot](decisions/0001-repository-operations-copilot.md)
- [ADR 0002: packaged desktop and GitHub
  first](decisions/0002-packaged-desktop-github-first.md)

## Development

- contributor onboarding: [development/onboarding.md](development/onboarding.md)
- local workflow: [development/workflow.md](development/workflow.md)
- testing guide: [development/testing.md](development/testing.md)
- desktop foundation implementation plan:
  [development/desktop-foundation.md](development/desktop-foundation.md)
- scope reduction and legacy retirement:
  [development/scope-reduction.md](development/scope-reduction.md)

## Runtime And Security

- local security model: [security/local-security-model.md](security/local-security-model.md)

## Documentation Rule

If a change affects behavior, contracts, setup or operational expectations,
update the nearest relevant document in this tree as part of the same change.
Distinguish current, transitional and target capabilities.
