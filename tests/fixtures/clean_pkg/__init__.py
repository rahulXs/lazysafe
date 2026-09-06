"""clean package with no side effects."""

import json

__all__ = ["get_data", "load_config"]


def load_config(path: str) -> dict:
    """load a config file."""
    with open(path) as f:
        return json.load(f)


def get_data() -> list[int]:
    """return some data."""
    return [1, 2, 3]
