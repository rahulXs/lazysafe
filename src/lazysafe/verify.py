"""compare one command's behaviour with and without process-wide lazy imports.

This is an experiment on a whole interpreter, not a check of a source edit.
Both runs must succeed, the interpreter must really defer imports, and output is
compared exactly: no normalization, so two runs that merely look alike cannot
pass. Nothing here proves a lazy import rewrite is safe.
"""

import subprocess
from dataclasses import dataclass

from lazysafe.capability import lazy_support

_TIMEOUT_S = 300


@dataclass
class RunResult:
    # None means the child never produced an exit code: it failed to start or timed out
    exit_code: int | None
    stdout: str
    stderr: str


@dataclass
class VerifyResult:
    equivalent: bool
    eager: RunResult
    lazy: RunResult
    diffs: list[str]
    error: str = ""


def _run_command(command, lazy=False, timeout=_TIMEOUT_S):
    # command is a literal argv; lazy mode goes right after the executable
    args = [command[0], *command[1:]]

    if lazy:
        args[1:1] = ["-X", "lazy_imports=all"]

    try:
        run = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return RunResult(exit_code=None, stdout="", stderr="executable not found")
    except subprocess.TimeoutExpired:
        return RunResult(exit_code=None, stdout="", stderr="timed out")
    except OSError as exc:
        return RunResult(exit_code=None, stdout="", stderr=str(exc))

    return RunResult(
        exit_code=run.returncode,
        stdout=run.stdout,
        stderr=run.stderr,
    )


def verify(command, *, timeout=_TIMEOUT_S):
    ok, reason = lazy_support(command[0])
    if not ok:
        return VerifyResult(
            equivalent=False,
            eager=RunResult(None, "", ""),
            lazy=RunResult(None, "", ""),
            diffs=[],
            error=reason,
        )

    eager = _run_command(command, lazy=False, timeout=timeout)
    lazy = _run_command(command, lazy=True, timeout=timeout)

    for name, side in (("eager", eager), ("lazy", lazy)):
        if side.exit_code is None:
            return VerifyResult(
                equivalent=False,
                eager=eager,
                lazy=lazy,
                diffs=[],
                error=f"the {name} run did not complete: {side.stderr}",
            )
        if side.exit_code != 0:
            return VerifyResult(
                equivalent=False,
                eager=eager,
                lazy=lazy,
                diffs=[],
                error=f"the {name} run exited {side.exit_code}; "
                "a comparison needs both runs to succeed",
            )

    diffs = []

    if eager.stdout != lazy.stdout:
        diffs.append("stdout differs")

    if eager.stderr != lazy.stderr:
        diffs.append("stderr differs")

    return VerifyResult(
        equivalent=not diffs,
        eager=eager,
        lazy=lazy,
        diffs=diffs,
    )
