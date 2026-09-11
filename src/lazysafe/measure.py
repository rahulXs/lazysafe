"""startup timing harness using -X importtime."""

import statistics
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class ModuleTiming:
    module: str
    cumulative_us: int
    self_us: int


@dataclass
class MeasureResult:
    entry_command: list[str]
    interpreter: str
    runs: dict[str, int]
    total_ms: dict[str, float]
    budget: dict[str, float | bool] | None = None
    per_module_top: list[ModuleTiming] = field(default_factory=list)


def _parse_importtime_line(line: str) -> tuple[int, int, str] | None:
    if not line.startswith("import time:"):
        return None

    parts = line.split("|")
    if len(parts) != 3:
        return None

    try:
        self_us = int(parts[0].split(":")[1].strip().replace("[us]", "").strip())
        cumulative_us = int(parts[1].strip().replace("[us]", "").strip())
        module = parts[2].strip()
    except (ValueError, IndexError):
        return None

    return cumulative_us, self_us, module


def _run_timed(
    command: list[str],
    python: str | None = None,
) -> tuple[float, list[ModuleTiming]]:
    exe = python or sys.executable

    if len(command) == 1 and not command[0].startswith("-"):
        cmd = [exe, "-X", "importtime", "-c", f"import {command[0]}"]
    else:
        cmd = [exe, "-X", "importtime", *command]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return -1.0, []
    except FileNotFoundError:
        return -1.0, []

    if result.returncode != 0:
        return -1.0, []

    total_us = 0
    modules = []

    for line in result.stderr.splitlines():
        parsed = _parse_importtime_line(line)
        if parsed:
            cumulative, self_us, module = parsed
            total_us = max(total_us, cumulative)
            modules.append(ModuleTiming(module=module, cumulative_us=cumulative, self_us=self_us))

    modules.sort(key=lambda m: m.cumulative_us, reverse=True)

    return total_us / 1000.0, modules


def measure(
    command: list[str],
    *,
    runs: int = 15,
    warmup: int = 2,
    budget_ms: float | None = None,
    python: str | None = None,
) -> MeasureResult:
    if runs < 1:
        raise ValueError("runs must be >= 1")
    if warmup < 0:
        raise ValueError("warmup must be >= 0")

    all_times = []
    all_modules = []

    total_runs = warmup + runs
    for i in range(total_runs):
        total_ms, modules = _run_timed(command, python=python)
        if i >= warmup:
            if total_ms >= 0:
                all_times.append(total_ms)
            if not all_modules and modules:
                all_modules = modules

    if not all_times:
        return MeasureResult(
            entry_command=command,
            interpreter=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            runs={"warmup": warmup, "measured": runs},
            total_ms={"p50": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0},
            budget={"limit_ms": budget_ms, "passed": False} if budget_ms is not None else None,
        )

    p50 = statistics.median(all_times)
    min_ms = min(all_times)
    max_ms = max(all_times)
    stdev = statistics.stdev(all_times) if len(all_times) > 1 else 0.0

    budget_result = None
    if budget_ms is not None:
        budget_result = {"limit_ms": budget_ms, "passed": p50 <= budget_ms}

    return MeasureResult(
        entry_command=command,
        interpreter=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        runs={"warmup": warmup, "measured": runs},
        total_ms={
            "p50": round(p50, 1),
            "min": round(min_ms, 1),
            "max": round(max_ms, 1),
            "stdev": round(stdev, 1),
        },
        budget=budget_result,
        per_module_top=[
            ModuleTiming(module=m.module, cumulative_us=m.cumulative_us, self_us=m.self_us)
            for m in all_modules[:20]
        ],
    )


def result_to_dict(result: MeasureResult) -> dict:
    return {
        "schema_version": 1,
        "entry_command": result.entry_command,
        "interpreter": result.interpreter,
        "mode": "eager",
        "runs": result.runs,
        "total_ms": result.total_ms,
        "budget": result.budget,
        "baseline_comparison": None,
        "per_module_top": [
            {
                "module": m.module,
                "cumulative_ms": round(m.cumulative_us / 1000.0, 1),
                "self_ms": round(m.self_us / 1000.0, 1),
            }
            for m in result.per_module_top
        ],
    }
