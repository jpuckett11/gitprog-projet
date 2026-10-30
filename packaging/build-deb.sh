#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-0.1.0}"
WORK="$(mktemp -d)"
PKG="gitget_${VERSION}_amd64"
ROOT="${WORK}/${PKG}"

if [[ ! -f dist/gitget ]]; then
    echo "Run pyinstaller first:  uv run pyinstaller packaging/gitget.spec" >&2
    exit 1
fi

install -Dm755 dist/gitget                "${ROOT}/opt/gitget/gitget"
install -Dm644 packaging/gitget.desktop   "${ROOT}/usr/share/applications/gitget.desktop"
mkdir -p "${ROOT}/usr/bin"
ln -s ../../opt/gitget/gitget "${ROOT}/usr/bin/gitget"

if [[ ! -f packaging/icons/gitget-256.png ]]; then
    uv run python packaging/render_pngs.py
fi
for size in 16 24 32 48 64 128 256 512; do
    install -Dm644 "packaging/icons/gitget-${size}.png" \
        "${ROOT}/usr/share/icons/hicolor/${size}x${size}/apps/gitget.png"
done
install -Dm644 src/gitget/assets/gitget.svg \
    "${ROOT}/usr/share/icons/hicolor/scalable/apps/gitget.svg"

install -Dm644 /dev/null "${ROOT}/DEBIAN/control"
cat > "${ROOT}/DEBIAN/control" <<EOF
Package: gitget
Version: ${VERSION}
Section: vcs
Priority: optional
Architecture: amd64
Maintainer: jpuckett11 <investigations@obsidianwatch.org>
Depends: libxcb-cursor0, libsecret-1-0
Description: Linux GitHub desktop client (Triage / Investigation / Admin)
 Triage notifications, run investigations as Discussions-backed cases,
 and administer org/repo settings — all from a single PySide6 desktop app.
EOF

dpkg-deb --build "${ROOT}" "./${PKG}.deb"
echo "Built: ${PKG}.deb"
