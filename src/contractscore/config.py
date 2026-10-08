from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT = Path(__file__).with_name("default_config.toml")


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT, "rb") as f:
        return tomllib.load(f)
