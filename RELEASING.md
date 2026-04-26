# Releasing

## Versioning

The current documented baseline aligns with application version `0.3.4` from [config/settings.py](config/settings.py).

## Release Checklist

1. Ensure docs are current.
2. Run:

```bash
make verify
make ui-smoke
./venv/bin/pip check
cd frontend && npm audit --audit-level=high
```

3. Review `CHANGELOG.md`.
4. Prepare release notes under `docs/releases/`.
5. Tag the release in git.
6. Publish the GitHub release.

## Current Release

The current public-readiness baseline should use:

```text
v0.3.4
```

With notes based on:
- [CHANGELOG.md](CHANGELOG.md)
- [docs/releases/v0.3.4.md](docs/releases/v0.3.4.md)
