"""clean package with no side effects."""

import json
import os
from pathlib import Path

__all__ = ["load_config", "get_data"]


def load_config(path: str) -> dict:
    """load a config file."""
    with open(path) as f:
        return json.load(f)


def get_data() -> list[int]:
    """return some data."""
    return [1, 2, 3]
