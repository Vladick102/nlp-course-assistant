"""Load config.yaml once; expose paths relative to the repo root."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@cache
def cfg() -> dict[str, Any]:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def path(key: str) -> Path:
    """Absolute path for an entry of `paths:` in config.yaml."""
    return ROOT / cfg()["paths"][key]
