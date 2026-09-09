"""configuration loading and merging."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    targets: list[str] = field(default_factory=lambda: ["src"])
    budget_ms: float | None = None
    measure_runs: int = 15
    measure_warmup: int = 2
    allowlist: list[str] = field(default_factory=list)


_KNOWN_KEYS = {
    "targets",
    "budget_ms",
    "measure_runs",
    "measure_warmup",
    "allowlist",
}


def load_config(project_root: Path) -> Config:
    """load lazysafe.toml from project root, falling back to defaults."""
    config = Config()
    config_path = project_root / "lazysafe.toml"

    if not config_path.exists():
        return config

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    unknown = set(raw.keys()) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"unknown config key: {unknown.pop()!r}")

    for key in _KNOWN_KEYS:
        if key in raw:
            setattr(config, key, raw[key])

    return config
