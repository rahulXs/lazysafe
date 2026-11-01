"""command-duration timing harness."""

import math
import statistics
import time
from dataclasses import dataclass, field

from lazysafe import process as process_runner
from lazysafe._version import __version__

_SAMPLE_TIMEOUT_DEFAULT = 30.0

BUDGET_UNAVAILABLE = (
    "budget gating is unavailable in this release: the reported metric is "
    "command duration, so a budget decision can be made."
)


@dataclass
class SampleError:
    sample: int
    phase: str
    kind: str
    detail: str


@dataclass
class _Sample:
    phase: str
    ok: bool
    duration_ms: float = 0.0
    duration_ns: int = 0
    returncode: int | None = None
    error_kind: str = ""
    error_detail: str = ""
    truncated: bool = False


@dataclass
class MeasureResult:
    entry_command: list[str]
    interpreter: str
    runs: dict[str, int]
    total_ms: dict[str, float] | None
    budget: object = None
    errors: list[SampleError] = field(default_factory=list)
    ok: bool = True
    samples: list[dict] = field(default_factory=list)
    outcome: str = "completed"


def _parse_importtime_line(line):
    """Retained for compatibility; importtime attribution is not used."""
    if not isinstance(line, str) or not line.startswith("import time:"):
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


def _run_one(command, timeout):
    outcome = process_runner.run(command, timeout=timeout)
    ok = (
        outcome.outcome == "exited"
        and outcome.returncode == 0
        and not outcome.stdout_truncated
        and not outcome.stderr_truncated
    )
    error_kind = ""
    error_detail = ""
    if not ok:
        if outcome.outcome == "spawn_error":
            error_kind = "spawn_error"
        elif outcome.outcome == "timeout":
            error_kind = "timeout"
        elif outcome.outcome == "signaled":
            error_kind = "signal"
        elif outcome.outcome == "interrupted":
            error_kind = "interrupted"
        elif outcome.stdout_truncated or outcome.stderr_truncated:
            error_kind = "output_overflow"
        elif outcome.returncode != 0:
            error_kind = "nonzero_exit"
        else:
            error_kind = outcome.outcome
        error_detail = outcome.detail
    return _Sample(
        phase="",
        ok=ok,
        duration_ms=outcome.elapsed_ns / 1_000_000.0,
        duration_ns=outcome.elapsed_ns,
        returncode=outcome.returncode,
        error_kind=error_kind,
        error_detail=error_detail,
        truncated=outcome.stdout_truncated or outcome.stderr_truncated,
    )


def measure(command, *, runs=15, warmup=2, budget_ms=None, timeout=_SAMPLE_TIMEOUT_DEFAULT):  # noqa: C901
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
        raise ValueError("runs must be >= 1")
    if isinstance(warmup, bool) or not isinstance(warmup, int) or warmup < 0:
        raise ValueError("warmup must be >= 0")
    if budget_ms is not None:
        if isinstance(budget_ms, bool) or not isinstance(budget_ms, (int, float)):
            raise ValueError("budget_ms must be a number")
        if not math.isfinite(budget_ms) or budget_ms < 0:
            raise ValueError("budget_ms must be finite and nonnegative")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("timeout must be a number")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")

    command = list(command)
    samples = []
    errors = []

    for i in range(warmup):
        sample = _run_one(command, timeout)
        sample.phase = "warmup"
        samples.append(sample)
        if not sample.ok:
            errors.append(
                SampleError(
                    sample=i, phase="warmup", kind=sample.error_kind, detail=sample.error_detail
                )
            )

    for i in range(runs):
        sample = _run_one(command, timeout)
        sample.phase = "measured"
        samples.append(sample)
        if not sample.ok:
            errors.append(
                SampleError(
                    sample=i, phase="measured", kind=sample.error_kind, detail=sample.error_detail
                )
            )

    warmup_ok = all(s.ok for s in samples if s.phase == "warmup")
    measured_ok = all(s.ok for s in samples if s.phase == "measured")
    all_ok = warmup_ok and measured_ok

    measured_durations = [s.duration_ns for s in samples if s.phase == "measured"]

    if all_ok and measured_durations:
        median_ns = statistics.median(measured_durations)
        min_ns = min(measured_durations)
        max_ns = max(measured_durations)
        deviations = [abs(x - median_ns) for x in measured_durations]
        mad_ns = statistics.median(deviations) if deviations else 0.0
        total_ms = {
            "p50": median_ns / 1_000_000.0,
            "min": min_ns / 1_000_000.0,
            "max": max_ns / 1_000_000.0,
            "mad": mad_ns / 1_000_000.0,
        }
    else:
        total_ms = None

    if budget_ms is None:
        budget = {"limit_ms": None, "status": "not_evaluated"}
    elif not all_ok or total_ms is None:
        budget = {"limit_ms": budget_ms, "status": "not_evaluated"}
    else:
        if total_ms["p50"] > budget_ms:
            budget = {"limit_ms": budget_ms, "status": "failed"}
        else:
            budget = {"limit_ms": budget_ms, "status": "passed"}

    ok = len(errors) == 0
    if budget.get("status") == "failed":
        outcome = "negative"
    elif not ok:
        outcome = "error"
    else:
        outcome = "completed"

    result = MeasureResult(
        entry_command=command,
        interpreter=command[0] if command else "",
        runs={
            "warmup": warmup,
            "measured": runs,
            "succeeded": sum(1 for s in samples if s.ok),
            "failed": sum(1 for s in samples if not s.ok),
        },
        total_ms=total_ms,
        budget=budget,
        errors=errors,
        ok=ok,
        samples=[
            {
                "phase": s.phase,
                "outcome": "completed" if s.ok else "error",
                "duration_ms": s.duration_ms,
                "returncode": s.returncode,
                "truncated": s.truncated,
            }
            for s in samples
        ],
        outcome=outcome,
    )
    return result


def result_to_dict(result):
    run_id = __import__("uuid").uuid4().hex
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    duration_ms = 0.0
    if result.total_ms:
        duration_ms = result.total_ms["p50"]

    errors = [
        {
            "code": "execution_error",
            "message": e.detail,
            "phase": e.phase,
            "path": None,
            "sample": e.sample,
            "kind": e.kind,
        }
        for e in result.errors
    ]

    report = {
        "schema_version": 2,
        "kind": "measurement",
        "tool": {"name": "lazysafe", "version": __version__},
        "outcome": result.outcome,
        "run": {
            "id": run_id,
            "timestamp_utc": timestamp,
            "duration_ms": duration_ms,
            "interpreter": result.interpreter,
        },
        "errors": errors,
        "coverage": {
            "supported": ["command_duration"],
            "unavailable": ["import_attribution", "saved_baseline"],
            "incomplete": [] if result.ok else ["execution_failure"],
        },
        "result": {
            "entry_command": result.entry_command,
            "interpreter": result.interpreter,
            "runs": result.runs,
            "total_ms": result.total_ms,
            "budget": result.budget,
            "samples": result.samples,
            "ok": result.ok,
        },
        # Backward-compatible flat fields.
        "entry_command": result.entry_command,
        "interpreter": result.interpreter,
        "mode": "command",
        "runs": result.runs,
        "total_ms": result.total_ms,
        "budget": result.budget,
        "ok": result.ok,
        "baseline_comparison": None,
        "per_module_top": [],
    }
    if not result.ok:
        report["errors"] = errors
    return report
