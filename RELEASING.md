# Releasing

This document is the release compliance checklist for DevSynapse AI.

## Current Release

The current public-readiness baseline is:

```text
v0.6.2
```

It aligns with application version `0.6.2` in [config/settings.py](config/settings.py)
and release notes in [docs/releases/v0.6.2.md](docs/releases/v0.6.2.md).

## Supported Targets

The supported shell installer and updater target is Linux on Debian/Ubuntu or
close `apt`-based derivatives.

Required system tools:
- `bash`
- `git`
- `python3`
- `python3-venv`
- `python3-pip`
- `nodejs`
- `npm`

The supported desktop targets are Linux x86_64 and Windows x86_64. Native
Windows source-checkout setup is not a supported shell workflow; there is no
PowerShell or `.bat` installer.

## Desktop Distribution Status

The desktop packaging flow is Tauri v2 plus a PyInstaller backend sidecar. The
current repository baseline has validated Linux and Windows desktop artifacts:

- `frontend/src-tauri/target/release/bundle/deb/DevSynapse AI_0.6.2_amd64.deb`
- `frontend/src-tauri/target/release/bundle/rpm/DevSynapse AI-0.6.2-1.x86_64.rpm`
- Windows NSIS installer generated on `windows-latest`

macOS bundles are configured in Tauri, but they are not validated release
artifacts until built and smoke-tested on macOS.

## Compliance Gate

Before tagging or updating a release, confirm:

- version references match `config/settings.py`, `README.md`, `CHANGELOG.md`,
  `RELEASING.md` and the target `docs/releases/<tag>.md`
- platform support is explicit: Debian/Ubuntu-style Linux shell install is
  supported; Linux and Windows desktop packages are validated; macOS is
  unvalidated
- API contract changes are reflected in `api/models.py`, `frontend/src/types.ts`,
  `frontend/src/api/client.ts` and `docs/api/overview.md`
- schema changes have migrations and data-model documentation
- security boundary changes are documented in `SECURITY.md` or
  `docs/security/local-security-model.md`
- runtime/setup/update behavior is documented in `README.md`,
  `docs/deployment/runtime.md` and `docs/development/onboarding.md`
- release notes state migration impact and validation evidence
- no secrets, local databases, logs or generated dependency directories are staged

## Validation Commands

Run the complete local gate:

```bash
make verify
make desktop-build
make ui-smoke
./venv/bin/pip check
cd frontend && npm audit --audit-level=high
```

Expected coverage:
- Ruff and backend tests
- shell syntax checks and utility script compilation
- frontend ESLint and production build
- Linux desktop `.deb`/`.rpm` packaging
- Windows desktop packaging through the GitHub release workflow
- Playwright UI smoke against a disposable runtime
- Python dependency consistency
- high-severity frontend dependency audit

## Publishing

1. Ensure `CHANGELOG.md` and the target release notes are current.
2. Commit all release preparation changes.
3. Create an annotated tag, for example:

```bash
git tag -a v0.6.2 -m "DevSynapse AI v0.6.2"
```

4. Push the tag:

```bash
git push origin v0.6.2
```

5. Confirm the GitHub release workflow publishes from
   `docs/releases/v0.6.2.md`.

## Post-Release Corrections

The release workflow intentionally leaves an existing GitHub release unchanged.
If release notes are clarified after publication, update the release body
explicitly after reviewing the diff:

```bash
gh release edit v0.6.2 --notes-file docs/releases/v0.6.2.md
```
