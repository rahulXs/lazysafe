"""trial scenario validation."""

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Scenario:
    name: str
    role: str
    command: list[str]
    comparison: str = "exact"


@dataclass
class TrialConfig:
    schema_version: int
    package: str
    source_root: str
    inputs: list[str] = field(default_factory=list)
    runs: int = 15
    warmup: int = 2
    timeout_seconds: float = 30.0
    scenarios: list[Scenario] = field(default_factory=list)


_ALLOWED_TOP_KEYS = {
    "schema_version",
    "package",
    "source_root",
    "inputs",
    "runs",
    "warmup",
    "timeout_seconds",
    "scenario",
}
_ALLOWED_SCENARIO_KEYS = {"name", "role", "command", "comparison"}
_VALID_ROLES = {"startup", "first_use", "check"}
_VALID_COMPARISONS = {"exact", "exit-code"}


def _is_name(value):
    return isinstance(value, str) and value and all(c.isalnum() or c in "_-" for c in value)


def parse_trial_config(path):  # noqa: C901
    path = Path(path)
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid scenario file: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("scenario file must be a TOML table")

    unknown = set(raw) - _ALLOWED_TOP_KEYS
    if unknown:
        raise ValueError(f"unknown scenario keys: {', '.join(sorted(unknown))}")

    for key in ("schema_version", "package", "source_root", "scenario"):
        if key not in raw:
            raise ValueError(f"missing required key: {key}")

    if raw["schema_version"] != 1:
        raise ValueError("unsupported schema_version")

    package = raw["package"]
    if not isinstance(package, str) or not package.isidentifier():
        raise ValueError("package must be an identifier")

    source_root = raw["source_root"]
    if not isinstance(source_root, str) or not source_root:
        raise ValueError("source_root must be a nonempty string")

    inputs = raw.get("inputs", [])
    if not isinstance(inputs, list) or any(not isinstance(x, str) for x in inputs):
        raise ValueError("inputs must be a list of strings")

    runs = raw.get("runs", 15)
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 3:
        raise ValueError("runs must be an integer >= 3")

    warmup = raw.get("warmup", 2)
    if isinstance(warmup, bool) or not isinstance(warmup, int) or warmup < 0:
        raise ValueError("warmup must be an integer >= 0")

    timeout = raw.get("timeout_seconds", 30.0)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("timeout_seconds must be finite and positive")

    scenarios_raw = raw["scenario"]
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("scenario must be a nonempty list")

    scenarios = []
    names = set()
    for entry in scenarios_raw:
        if not isinstance(entry, dict):
            raise ValueError("scenario entry must be a table")
        unknown_s = set(entry) - _ALLOWED_SCENARIO_KEYS
        if unknown_s:
            raise ValueError(f"unknown scenario keys: {', '.join(sorted(unknown_s))}")
        for key in ("name", "role", "command"):
            if key not in entry:
                raise ValueError(f"scenario missing {key}")
        name = entry["name"]
        if not _is_name(name):
            raise ValueError("invalid scenario name")
        if name in names:
            raise ValueError("duplicate scenario name")
        names.add(name)
        role = entry["role"]
        if role not in _VALID_ROLES:
            raise ValueError("invalid scenario role")
        command = entry["command"]
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(x, str) for x in command)
        ):
            raise ValueError("command must be a nonempty list of strings")
        comparison = entry.get("comparison", "exact")
        if comparison not in _VALID_COMPARISONS:
            raise ValueError("invalid comparison")
        scenarios.append(Scenario(name=name, role=role, command=command, comparison=comparison))

    if not any(s.role == "startup" for s in scenarios):
        raise ValueError("at least one startup scenario is required")
    if not any(s.role == "first_use" for s in scenarios):
        raise ValueError("at least one first_use scenario is required")

    return TrialConfig(
        schema_version=raw["schema_version"],
        package=package,
        source_root=source_root,
        inputs=inputs,
        runs=runs,
        warmup=warmup,
        timeout_seconds=float(timeout),
        scenarios=scenarios,
    )
