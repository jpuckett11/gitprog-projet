#!/usr/bin/env bash
# Build a .deb that wraps the PyInstaller binary.
#
# Usage:
#   ./packaging/build-deb.sh [VERSION]
#
# Requires: dpkg-deb. Produces gitget_<version>_amd64.deb in the project root.

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

# /opt/gitget/gitget   the binary
# /usr/bin/gitget          symlink
# /usr/share/applications/...  .desktop file
# /usr/share/icons/.../gitget.png   icon (placeholder)
install -Dm755 dist/gitget                "${ROOT}/opt/gitget/gitget"
install -Dm644 packaging/gitget.desktop   "${ROOT}/usr/share/applications/gitget.desktop"
mkdir -p "${ROOT}/usr/bin"
ln -s ../../opt/gitget/gitget "${ROOT}/usr/bin/gitget"

# placeholder icon — replace with a real PNG before publishing
install -Dm644 /dev/null "${ROOT}/usr/share/icons/hicolor/256x256/apps/gitget.png"

# control file
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
