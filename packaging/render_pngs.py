"""Rasterize the bundled SVG icon to PNGs at standard sizes.

Run with:
    uv run python packaging/render_pngs.py

Produces packaging/icons/gitget-<size>.png at sizes 16, 24, 32, 48, 64, 128, 256, 512.
Build scripts (.deb/AppImage) consume these.

Uses PySide6's QSvgRenderer — no extra system dependency needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def main() -> int:
    here = Path(__file__).resolve().parent
    svg_path = here.parent / "src" / "gitget" / "assets" / "gitget.svg"
    out_dir = here / "icons"
    out_dir.mkdir(exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        print(f"failed to load SVG at {svg_path}", file=sys.stderr)
        return 1

    for size in SIZES:
        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        out = out_dir / f"gitget-{size}.png"
        image.save(str(out), "PNG")
        print(f"  wrote {out} ({size}x{size})")

    print(f"\n{len(SIZES)} PNGs in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
