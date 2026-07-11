#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INPUT_DIR="${1:-$ROOT_DIR/frontend/src-tauri/target/release/bundle/deb}"
OUTPUT_DIR="${2:-$ROOT_DIR/artifacts/apt}"
CODENAME="${APT_CODENAME:-stable}"
COMPONENT="${APT_COMPONENT:-main}"
ARCHITECTURE="${APT_ARCHITECTURE:-amd64}"
ORIGIN="${APT_ORIGIN:-DevSynapse AI}"
LABEL="${APT_LABEL:-DevSynapse AI}"
REQUIRE_GPG="${APT_REQUIRE_GPG:-0}"

if ! command -v dpkg-scanpackages >/dev/null 2>&1; then
    echo "dpkg-scanpackages is required. Install dpkg-dev on Debian/Ubuntu." >&2
    exit 1
fi

mapfile -t DEBS < <(find "$INPUT_DIR" -maxdepth 1 -type f -name '*.deb' | sort)
if [ "${#DEBS[@]}" -eq 0 ]; then
    echo "No .deb packages found in $INPUT_DIR" >&2
    exit 1
fi

REPO_ROOT="$OUTPUT_DIR/repository"
POOL_DIR="$REPO_ROOT/pool/$COMPONENT"
BINARY_DIR="$REPO_ROOT/dists/$CODENAME/$COMPONENT/binary-$ARCHITECTURE"
mkdir -p "$POOL_DIR" "$BINARY_DIR"
cp "${DEBS[@]}" "$POOL_DIR/"

(
    cd "$REPO_ROOT"
    dpkg-scanpackages --arch "$ARCHITECTURE" "pool/$COMPONENT" > \
        "dists/$CODENAME/$COMPONENT/binary-$ARCHITECTURE/Packages"
    gzip -9cn "dists/$CODENAME/$COMPONENT/binary-$ARCHITECTURE/Packages" > \
        "dists/$CODENAME/$COMPONENT/binary-$ARCHITECTURE/Packages.gz"
)

PACKAGES_SIZE="$(wc -c < "$BINARY_DIR/Packages")"
PACKAGES_SHA256="$(sha256sum "$BINARY_DIR/Packages" | awk '{print $1}')"
PACKAGES_GZ_SIZE="$(wc -c < "$BINARY_DIR/Packages.gz")"
PACKAGES_GZ_SHA256="$(sha256sum "$BINARY_DIR/Packages.gz" | awk '{print $1}')"
DATE_RFC2822="$(date -Ru)"

cat > "$REPO_ROOT/dists/$CODENAME/Release" <<EOF
Origin: $ORIGIN
Label: $LABEL
Suite: $CODENAME
Codename: $CODENAME
Date: $DATE_RFC2822
Architectures: $ARCHITECTURE
Components: $COMPONENT
Description: DevSynapse AI desktop APT repository
SHA256:
 $PACKAGES_SHA256 $PACKAGES_SIZE $COMPONENT/binary-$ARCHITECTURE/Packages
 $PACKAGES_GZ_SHA256 $PACKAGES_GZ_SIZE $COMPONENT/binary-$ARCHITECTURE/Packages.gz
EOF

SIGNING_KEY="${APT_GPG_KEY_ID:-}"
if [ -n "${APT_GPG_PRIVATE_KEY:-}" ]; then
    printf '%s' "$APT_GPG_PRIVATE_KEY" | gpg --batch --import
fi

if [ -z "$SIGNING_KEY" ] && gpg --batch --list-secret-keys >/dev/null 2>&1; then
    SIGNING_KEY="$(gpg --batch --list-secret-keys --with-colons | awk -F: '$1 == "fpr" {print $10; exit}')"
fi

if [ "$REQUIRE_GPG" = "1" ] && [ -z "$SIGNING_KEY" ]; then
    echo "APT signing is required, but no signing key is available." >&2
    exit 1
fi

if [ -n "$SIGNING_KEY" ]; then
    gpg --batch --yes --armor --detach-sign \
        --local-user "$SIGNING_KEY" \
        --output "$REPO_ROOT/dists/$CODENAME/Release.gpg" \
        "$REPO_ROOT/dists/$CODENAME/Release"
    gpg --batch --yes --clearsign \
        --local-user "$SIGNING_KEY" \
        --output "$REPO_ROOT/dists/$CODENAME/InRelease" \
        "$REPO_ROOT/dists/$CODENAME/Release"
    gpg --batch --yes --armor --export "$SIGNING_KEY" > \
        "$OUTPUT_DIR/devsynapse-apt-signing-key.asc"
    cp "$OUTPUT_DIR/devsynapse-apt-signing-key.asc" "$REPO_ROOT/devsynapse-apt-signing-key.asc"
fi

tar -C "$OUTPUT_DIR" -czf "$OUTPUT_DIR/devsynapse-apt-repository.tar.gz" repository
echo "APT repository built: $OUTPUT_DIR/devsynapse-apt-repository.tar.gz"
