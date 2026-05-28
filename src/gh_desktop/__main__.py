"""CLI entry point: `gh-desktop`."""

from __future__ import annotations

import sys

from gh_desktop.app import run


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
