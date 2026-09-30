"""verify behavioral equivalence between eager and lazy modes."""

import re
import subprocess
import sys
from dataclasses import dataclass

_DEFAULT_NORMALIZATIONS = [
    (r"\d+\.\d+ms", "Xms"),
    (r"\d+\.\d+s", "Xs"),
    (r"/tmp/[^\s]+", "TMP_PATH"),
    (r"C:\\[^\s]+", "WIN_PATH"),
    (r"0x[0-9a-f]+", "0xADDR"),
    (r"running on Python \d+\.\d+\.\d+", "running on Python X.Y.Z"),
]


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class VerifyResult:
    equivalent: bool
    eager: RunResult
    lazy: RunResult
    diffs: list[str]


def _normalize(text, patterns=None):
    result = text
    for pattern, replacement in (patterns or _DEFAULT_NORMALIZATIONS):
        result = re.sub(pattern, replacement, result)
    return result


def _run_command(command, python, lazy=False, timeout=300):
    args = [python]

    if lazy:
        args.extend(["-X", "lazy_imports=all"])

    args.extend(command)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return RunResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired:
        return RunResult(exit_code=-1, stdout="", stderr="timeout")
    except FileNotFoundError:
        return RunResult(exit_code=-2, stdout="", stderr=f"python not found: {python}")


def verify(command, *, python=None, lazy_python=None):
    exe = python or sys.executable
    lazy_exe = lazy_python or exe

    eager = _run_command(command, exe, lazy=False)
    lazy = _run_command(command, lazy_exe, lazy=True)

    diffs = []

    if eager.exit_code != lazy.exit_code:
        diffs.append(
            f"exit code: eager={eager.exit_code} lazy={lazy.exit_code}"
        )

    norm_eager_stdout = _normalize(eager.stdout)
    norm_lazy_stdout = _normalize(lazy.stdout)
    if norm_eager_stdout != norm_lazy_stdout:
        diffs.append("stdout differs after normalization")

    norm_eager_stderr = _normalize(eager.stderr)
    norm_lazy_stderr = _normalize(lazy.stderr)
    if norm_eager_stderr != norm_lazy_stderr:
        diffs.append("stderr differs after normalization")

    return VerifyResult(
        equivalent=len(diffs) == 0,
        eager=eager,
        lazy=lazy,
        diffs=diffs,
    )
