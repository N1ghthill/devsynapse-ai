# Release Packaging

## Status

The release pipeline is current production infrastructure. It replaces any
normal-user installation flow that asks people to clone the repository, install
Python, run a backend process or start the frontend manually.

## User-Facing Artifacts

The `Release Packages` GitHub Actions workflow builds:

- Linux `.deb` for Debian/Ubuntu package installation;
- Linux AppImage for portable installation;
- Windows NSIS `.exe` installer;
- Windows MSI package;
- `latest.json` for the Tauri updater;
- an APT repository archive generated from the Linux `.deb`;
- `devsynapse-apt-signing-key.asc` when the APT repository is signed.

The Python backend is bundled as a Tauri external binary. A production user
launches one installed desktop app; the backend starts and stops with that app.

## Release Trigger

Create a version tag:

```bash
git tag v1.2.7
git push origin v1.2.7
```

The workflow builds packages on native operating-system runners and attaches
the release assets to the GitHub release. Publication also depends on a Linux
install smoke test that installs the generated `.deb` and verifies the desktop
binary, backend sidecar and desktop entry. Manual dispatch is available for
release dry runs, but production publication is tag-driven.

## Required Secrets And Variables

GitHub repository secrets:

- `TAURI_SIGNING_PRIVATE_KEY`: Tauri updater private key content or key path
  accepted by the Tauri CLI.
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`: optional password for the updater key.
- `APT_GPG_PRIVATE_KEY`: optional private key for signing APT metadata.
- `APT_GPG_KEY_ID`: optional key id used when signing APT metadata. If omitted,
  the packaging script derives the first imported secret-key fingerprint.

GitHub repository variables:

- `DEVSYNAPSE_UPDATER_PUBLIC_KEY`: public key embedded into the release build.
- `DEVSYNAPSE_UPDATER_ENDPOINT`: updater manifest URL. Default if omitted in
  local reasoning is the latest GitHub release asset URL:
  `https://github.com/N1ghthill/devsynapse-ai/releases/latest/download/latest.json`.
- `DEVSYNAPSE_APT_REQUIRE_GPG`: set to `1` to fail release builds when the APT
  repository cannot be signed.

The workflow also accepts legacy names `TAURI_UPDATER_PUBKEY` and
`TAURI_UPDATER_ENDPOINT` for compatibility with older repository settings.

Production Windows distribution also requires platform signing credentials
before broad external distribution:

- Windows code-signing certificate and timestamp configuration.

Those credentials are intentionally not committed to the repository. macOS is
not a supported distribution target.

## Linux APT Repository

The workflow uploads `devsynapse-apt-repository.tar.gz` and, on tag releases,
publishes the extracted repository to GitHub Pages at:

```text
https://n1ghthill.github.io/devsynapse-ai/apt
```

The repository layout is:

```text
repository/
  devsynapse-apt-signing-key.asc
  pool/main/*.deb
  dists/stable/Release
  dists/stable/InRelease
  dists/stable/Release.gpg
  dists/stable/main/binary-amd64/Packages
  dists/stable/main/binary-amd64/Packages.gz
```

`InRelease` and `Release.gpg` are present when an APT signing key is available.
Set `DEVSYNAPSE_APT_REQUIRE_GPG=1` after configuring `APT_GPG_PRIVATE_KEY` to
prevent unsigned APT repository artifacts from being published.

When signed, the public key is also published as the release asset
`devsynapse-apt-signing-key.asc` for repository bootstrap.

End-user APT setup:

```bash
curl -fsSL https://n1ghthill.github.io/devsynapse-ai/apt/devsynapse-apt-signing-key.asc \
  | sudo gpg --dearmor -o /usr/share/keyrings/devsynapse-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/devsynapse-archive-keyring.gpg] https://n1ghthill.github.io/devsynapse-ai/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/devsynapse.list
sudo apt update
sudo apt install dev-synapse-ai
```

## Updater Verification Checklist

The Tauri updater is the supported in-app update path for the Linux AppImage
and Windows NSIS installer artifacts. Debian/Ubuntu `.deb` installations should
receive updates through the published APT repository instead of relying on the
in-app updater.

Do not present the in-app updater as supported for Debian package installs.
The Tauri Linux updater artifact is the AppImage; a `.deb` install should show
APT/manual package guidance and link users to the latest release until a hosted
APT repository is available.

Before declaring a release channel healthy, verify:

- the release contains `latest.json`;
- `latest.json` lists `linux-x86_64` and `windows-x86_64`;
- each updater platform points to the staged release asset, not an Actions
  artifact URL;
- each updater asset has a matching `.sig` file;
- a production build embeds the expected updater public key and endpoint through
  `frontend/src-tauri/tauri.release.conf.json`;
- Settings shows the current application version and reports "up to date" when
  no newer signed release exists;
- Settings reports a clear failure when the manifest URL or signature is
  invalid.

Manual AppImage smoke:

1. Download the previous release AppImage, for example `v1.2.4`.
2. Mark it executable and launch it from a clean temporary app data directory.
3. Open Settings and select `Check for updates`.
4. Confirm the app detects the latest release, downloads the signed AppImage,
   installs it and relaunches.
5. Confirm Settings shows the new version after relaunch.

Manual Windows NSIS smoke:

1. Install the previous release NSIS `.exe` in a disposable Windows VM.
2. Launch DevSynapse AI and open Settings.
3. Select `Check for updates`.
4. Confirm the updater downloads the latest signed NSIS package, installs it
   passively and relaunches.
5. Confirm Windows Apps and DevSynapse Settings both show the new version.

Manual Debian/Ubuntu smoke:

1. Install the previous `.deb`.
2. Confirm Settings reports `APT or manual .deb` instead of enabling the Tauri
   updater button.
3. Install the latest release `.deb` manually with
   `sudo apt install ./DevSynapse-AI_<version>_linux-x86_64.deb`.
4. Confirm the desktop app launches with the new version.
5. After the `gh-pages` deployment finishes, add the repository and signing key.
6. Run `apt update`.
7. Confirm `apt policy dev-synapse-ai` sees the latest release.
8. Run `apt install dev-synapse-ai` and confirm the desktop app launches with
   the new version.

## Local Maintainer Commands

Build the backend sidecar for the current host:

```bash
python scripts/build_backend.py
```

Build Linux desktop packages from a Linux development machine:

```bash
cd frontend
npm ci
npm run desktop:build:linux
```

Generate an APT repository from built Debian packages:

```bash
bash scripts/build-apt-repository.sh
```

These commands are maintainer workflows only. Normal users install the produced
package for their operating system.
