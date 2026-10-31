"""load lazysafe.toml."""

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


# Keys recognized for migration diagnostics. Only ``targets`` is active in 0.7.
_SUPPORTED_KEYS = {"targets"}
_REMOVED_KEYS = {"allowlist"}
_INACTIVE_KEYS = {"budget_ms", "measure_runs", "measure_warmup"}
_KNOWN_KEYS = _SUPPORTED_KEYS | _REMOVED_KEYS | _INACTIVE_KEYS


def _format_keys(keys):
    return ", ".join(repr(key) for key in sorted(keys))


def load_config(project_root):
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

    inactive = set(raw) & _INACTIVE_KEYS
    if inactive:
        raise ValueError(
            "inactive config keys: "
            f"{_format_keys(inactive)} "
            "(measurement settings are restored with measure in 0.8.0)"
        )

    if "targets" in raw:
        targets = raw["targets"]
        if isinstance(targets, str) or not isinstance(targets, list):
            raise ValueError("config 'targets' must be a list of strings")
        if any(not isinstance(item, str) for item in targets):
            raise ValueError("config 'targets' must contain only strings")
        config.targets = list(targets)

    return config
