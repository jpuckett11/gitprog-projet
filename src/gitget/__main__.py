"""CLI entry point: `gitget`."""

from __future__ import annotations

import sys

from gitget.app import run


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
