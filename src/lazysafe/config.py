"""load lazysafe.toml."""

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    targets: list[str] = field(default_factory=lambda: ["src"])
    budget_ms: float | None = None
    measure_runs: int = 15
    measure_warmup: int = 2
    timeout_seconds: float = 30.0
    allowlist: list[str] = field(default_factory=list)


# Keys recognized for migration diagnostics. Only ``targets`` is active in 0.7.
_SUPPORTED_KEYS = {"targets", "budget_ms", "measure_runs", "measure_warmup", "timeout_seconds"}
_REMOVED_KEYS = {"allowlist"}
_INACTIVE_KEYS = set()
_KNOWN_KEYS = _SUPPORTED_KEYS | _REMOVED_KEYS | _INACTIVE_KEYS


def _format_keys(keys):
    return ", ".join(repr(key) for key in sorted(keys))


def load_config(project_root):  # noqa: C901
    """load and validate cwd ``lazysafe.toml``, falling back to defaults."""
    config = Config()
    config_path = Path(project_root) / "lazysafe.toml"

    if not config_path.exists():
        return config

    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in lazysafe.toml: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("lazysafe.toml must contain a TOML table")

    unknown = set(raw) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {_format_keys(unknown)}")

    if "allowlist" in raw:
        raise ValueError(
            "removed config key: 'allowlist' (allowlists have no effect in this release)"
        )

    if "targets" in raw:
        targets = raw["targets"]
        if isinstance(targets, str) or not isinstance(targets, list):
            raise ValueError("config 'targets' must be a list of strings")
        if any(not isinstance(item, str) for item in targets):
            raise ValueError("config 'targets' must contain only strings")
        config.targets = list(targets)

    if "budget_ms" in raw:
        value = raw["budget_ms"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("config 'budget_ms' must be a number or null")
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("config 'budget_ms' must be finite and nonnegative")
        config.budget_ms = value

    if "measure_runs" in raw:
        value = raw["measure_runs"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("config 'measure_runs' must be an integer")
        if value < 1:
            raise ValueError("config 'measure_runs' must be >= 1")
        config.measure_runs = value

    if "measure_warmup" in raw:
        value = raw["measure_warmup"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("config 'measure_warmup' must be an integer")
        if value < 0:
            raise ValueError("config 'measure_warmup' must be >= 0")
        config.measure_warmup = value

    if "timeout_seconds" in raw:
        value = raw["timeout_seconds"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("config 'timeout_seconds' must be a number")
        if not math.isfinite(value) or value <= 0:
            raise ValueError("config 'timeout_seconds' must be finite and positive")
        config.timeout_seconds = float(value)

    return config
