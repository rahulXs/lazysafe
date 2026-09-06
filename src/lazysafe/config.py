"""configuration loading and merging."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """lazysafe configuration."""

    targets: list[str] = field(default_factory=lambda: ["src"])
    budget_ms: float | None = None
    measure_runs: int = 15
    measure_warmup: int = 2
    probe_timeout: float = 30.0
    apply_mode: str = "dunder"
    allowlist: list[str] = field(default_factory=list)


def load_config(project_root: Path) -> Config:
    """load lazysafe.toml from project root, falling back to defaults."""
    config = Config()
    config_path = project_root / "lazysafe.toml"

    if not config_path.exists():
        return config

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    known_keys = {
        "targets",
        "budget_ms",
        "measure_runs",
        "measure_warmup",
        "probe_timeout",
        "apply_mode",
        "allowlist",
    }

    for key in raw:
        if key not in known_keys:
            raise ValueError(f"unknown config key: {key!r}")

    if "targets" in raw:
        config.targets = raw["targets"]
    if "budget_ms" in raw:
        config.budget_ms = raw["budget_ms"]
    if "measure_runs" in raw:
        config.measure_runs = raw["measure_runs"]
    if "measure_warmup" in raw:
        config.measure_warmup = raw["measure_warmup"]
    if "probe_timeout" in raw:
        config.probe_timeout = raw["probe_timeout"]
    if "apply_mode" in raw:
        config.apply_mode = raw["apply_mode"]
    if "allowlist" in raw:
        config.allowlist = raw["allowlist"]

    return config
