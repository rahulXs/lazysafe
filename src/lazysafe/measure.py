"""import-profile timing harness using -X importtime."""

import statistics
import subprocess
import sys
from dataclasses import dataclass, field

_SAMPLE_TIMEOUT_S = 60

BUDGET_UNAVAILABLE = (
    "budget gating is unavailable in this release: the reported metric is "
    "import-profile data, not command duration, so no budget decision can be made."
)


@dataclass
class ModuleTiming:
    module: str
    cumulative_us: int
    self_us: int


@dataclass
class SampleError:
    sample: int
    phase: str
    kind: str
    detail: str


@dataclass
class _Sample:
    ok: bool
    duration_ms: float = 0.0
    modules: list[ModuleTiming] = field(default_factory=list)
    error_kind: str = ""
    error_detail: str = ""


@dataclass
class MeasureResult:
    entry_command: list[str]
    interpreter: str
    runs: dict[str, int]
    total_ms: dict[str, float] | None
    budget: dict[str, float | bool] | None = None
    per_module_top: list[ModuleTiming] = field(default_factory=list)
    errors: list[SampleError] = field(default_factory=list)
    ok: bool = True


def _parse_importtime_line(line):
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


def _run_sample(command, python=None):
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
            timeout=_SAMPLE_TIMEOUT_S,
        )
    except OSError as exc:
        return _Sample(ok=False, error_kind="spawn_error", error_detail=str(exc))
    except subprocess.TimeoutExpired:
        return _Sample(
            ok=False,
            error_kind="timeout",
            error_detail=f"no exit within {_SAMPLE_TIMEOUT_S}s",
        )

    if result.returncode != 0:
        return _Sample(
            ok=False,
            error_kind="nonzero_exit",
            error_detail=f"exit {result.returncode}",
        )

    total_us = 0
    modules = []

    for line in result.stderr.splitlines():
        parsed = _parse_importtime_line(line)
        if parsed:
            cumulative, self_us, module = parsed
            total_us = max(total_us, cumulative)
            modules.append(ModuleTiming(module=module, cumulative_us=cumulative, self_us=self_us))

    modules.sort(key=lambda m: m.cumulative_us, reverse=True)

    return _Sample(ok=True, duration_ms=total_us / 1000.0, modules=modules)


def measure(
    command,
    *,
    runs=15,
    warmup=2,
    budget_ms=None,
    python=None,
):
    if runs < 1:
        raise ValueError("runs must be >= 1")
    if warmup < 0:
        raise ValueError("warmup must be >= 0")
    if budget_ms is not None:
        raise ValueError(BUDGET_UNAVAILABLE)

    measured_times = []
    first_modules = []
    errors = []
    succeeded = 0
    failed = 0

    total_runs = warmup + runs
    for i in range(total_runs):
        phase = "warmup" if i < warmup else "measured"
        sample = _run_sample(command, python=python)
        if sample.ok:
            succeeded += 1
            if phase == "measured":
                measured_times.append(sample.duration_ms)
            if not first_modules and sample.modules:
                first_modules = sample.modules
        else:
            failed += 1
            errors.append(
                SampleError(
                    sample=i, phase=phase, kind=sample.error_kind, detail=sample.error_detail
                )
            )

    ok = failed == 0

    total_ms = None
    if ok:
        p50 = statistics.median(measured_times)
        total_ms = {
            "p50": round(p50, 1),
            "min": round(min(measured_times), 1),
            "max": round(max(measured_times), 1),
            "stdev": round(statistics.stdev(measured_times), 1) if len(measured_times) > 1 else 0.0,
        }

    return MeasureResult(
        entry_command=command,
        interpreter=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        runs={"warmup": warmup, "measured": runs, "succeeded": succeeded, "failed": failed},
        total_ms=total_ms,
        budget=None,
        per_module_top=[
            ModuleTiming(module=m.module, cumulative_us=m.cumulative_us, self_us=m.self_us)
            for m in first_modules[:20]
        ]
        if ok
        else [],
        errors=errors,
        ok=ok,
    )


def result_to_dict(result):
    return {
        "schema_version": 1,
        "metric": "import_profile_max_cumulative_ms",
        "metric_note": "import-profile data from -X importtime; not command duration",
        "entry_command": result.entry_command,
        "interpreter": result.interpreter,
        "mode": "eager",
        "runs": result.runs,
        "total_ms": result.total_ms,
        "budget": result.budget,
        "ok": result.ok,
        "errors": [
            {"sample": e.sample, "phase": e.phase, "kind": e.kind, "detail": e.detail}
            for e in result.errors
        ],
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
