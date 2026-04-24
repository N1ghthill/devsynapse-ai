# Releasing

## Versioning

The current documented baseline aligns with application version `0.2.0` from [config/settings.py](config/settings.py).

## Release Checklist

1. Ensure docs are current.
2. Run:

```bash
./venv/bin/pytest -q
cd frontend && npm run build
```

3. Review `CHANGELOG.md`.
4. Prepare release notes under `docs/releases/`.
5. Tag the release in git.
6. Publish the GitHub release.

## Initial Release

The first public baseline should use:

```text
v0.2.0
```

With notes based on:
- [CHANGELOG.md](CHANGELOG.md)
- [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md)
