
from __future__ import annotations

from importlib import resources
from pathlib import Path


def asset_path(name: str) -> Path:
    with resources.as_file(resources.files(__package__).joinpath(name)) as p:
        return Path(p)


ICON_SVG = "gitget.svg"


def icon_path() -> Path:
    return asset_path(ICON_SVG)
