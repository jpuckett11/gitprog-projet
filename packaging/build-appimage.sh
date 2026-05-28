#!/usr/bin/env bash
# Build an AppImage from the PyInstaller output.
#
# Requires: appimagetool (https://github.com/AppImage/AppImageKit/releases).
# Usage: ./packaging/build-appimage.sh [VERSION]

set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-0.1.0}"

if [[ ! -f dist/gh-desktop ]]; then
    echo "Run pyinstaller first:  uv run pyinstaller packaging/gh-desktop.spec" >&2
    exit 1
fi

APPDIR="$(mktemp -d)/gh-desktop.AppDir"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

install -Dm755 dist/gh-desktop                "${APPDIR}/usr/bin/gh-desktop"
install -Dm644 packaging/gh-desktop.desktop   "${APPDIR}/gh-desktop.desktop"
install -Dm644 packaging/gh-desktop.desktop   "${APPDIR}/usr/share/applications/gh-desktop.desktop"
install -Dm644 /dev/null                      "${APPDIR}/gh-desktop.png"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
SELF="$(readlink -f "$0")"
HERE="$(dirname "${SELF}")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/gh-desktop" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

OUTPUT="gh-desktop-${VERSION}-x86_64.AppImage"
ARCH=x86_64 appimagetool "${APPDIR}" "${OUTPUT}"
echo "Built: ${OUTPUT}"
