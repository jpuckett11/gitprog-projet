#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-0.1.0}"

if [[ ! -f dist/gitget ]]; then
    echo "Run pyinstaller first:  uv run pyinstaller packaging/gitget.spec" >&2
    exit 1
fi

APPDIR="$(mktemp -d)/gitget.AppDir"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

install -Dm755 dist/gitget                "${APPDIR}/usr/bin/gitget"
install -Dm644 packaging/gitget.desktop   "${APPDIR}/gitget.desktop"
install -Dm644 packaging/gitget.desktop   "${APPDIR}/usr/share/applications/gitget.desktop"

if [[ ! -f packaging/icons/gitget-256.png ]]; then
    uv run python packaging/render_pngs.py
fi
install -Dm644 packaging/icons/gitget-256.png "${APPDIR}/gitget.png"
install -Dm644 packaging/icons/gitget-256.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/gitget.png"
install -Dm644 src/gitget/assets/gitget.svg   "${APPDIR}/usr/share/icons/hicolor/scalable/apps/gitget.svg"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
SELF="$(readlink -f "$0")"
HERE="$(dirname "${SELF}")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/gitget" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

OUTPUT="gitget-${VERSION}-x86_64.AppImage"
ARCH=x86_64 appimagetool "${APPDIR}" "${OUTPUT}"
echo "Built: ${OUTPUT}"
