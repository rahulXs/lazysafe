"""run one command and report how it ended.

All lazysafe command execution goes through this runner so a timeout, signal or
spawn failure can never be mistaken for a successful run. Output is captured as
raw bytes and is never decoded before comparison.
"""

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

DEFAULT_CAPTURE_LIMIT = 1 << 20  # 1 MiB per stream


@dataclass
class ProcessOutcome:
    argv: list
    outcome: str
    kind: str
    returncode: int | None
    exit_code: int | None
    stdout: bytes = b""
    stderr: bytes = b""
    stdout_bytes: bytes = b""
    stderr_bytes: bytes = b""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    elapsed_ns: int = 0
    cleanup_scope: str = "direct_child_only"
    detail: str = ""

    @property
    def ok(self):
        return self.outcome == "exited" and self.returncode == 0


def _reader(pipe, sink, limit, truncated):
    """Read raw bytes until EOF, recording whether the limit was exceeded."""
    total = bytearray()
    over = False
    try:
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                break
            if not over:
                if len(total) + len(chunk) > limit:
                    total.extend(chunk[: max(0, limit - len(total))])
                    over = True
                else:
                    total.extend(chunk)
    finally:
        with __import__("contextlib").suppress(OSError):
            pipe.close()
    sink.append(bytes(total))
    truncated.append(over)


def _terminate(proc, scope):
    if scope == "process_group" and hasattr(os, "killpg"):
        with contextlib.suppress(ProcessLookupError, OSError):
            os.killpg(proc.pid, signal.SIGTERM)
    else:
        with __import__("contextlib").suppress(OSError):
            proc.terminate()


def run(argv, *, timeout, cwd=None, env=None, capture_limit=DEFAULT_CAPTURE_LIMIT):  # noqa: C901
    """Run argv once. Never raises for an ordinary failed run."""
    argv = list(argv)
    started = time.monotonic_ns()
    cleanup_scope = (
        "process_group"
        if (sys.platform != "win32" and hasattr(os, "setsid"))
        else "direct_child_only"
    )

    stdout_sink = []
    stderr_sink = []
    stdout_trunc = []
    stderr_trunc = []

    try:
        popen_kwargs = {
            "args": argv,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": cwd,
            "env": env,
            "shell": False,
        }
        if cleanup_scope == "process_group":
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(**popen_kwargs)
    except (OSError, ValueError) as exc:
        return ProcessOutcome(
            argv=argv,
            outcome="spawn_error",
            kind="spawn_error",
            returncode=None,
            exit_code=None,
            stdout=b"",
            stderr=b"",
            stdout_bytes=b"",
            stderr_bytes=b"",
            elapsed_ns=time.monotonic_ns() - started,
            cleanup_scope=cleanup_scope,
            detail=str(exc),
        )

    t_out = threading.Thread(
        target=_reader, args=(proc.stdout, stdout_sink, capture_limit, stdout_trunc), daemon=True
    )
    t_err = threading.Thread(
        target=_reader, args=(proc.stderr, stderr_sink, capture_limit, stderr_trunc), daemon=True
    )
    t_out.start()
    t_err.start()

    interrupted = False
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate(proc, cleanup_scope)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                if cleanup_scope == "process_group" and hasattr(os, "killpg"):
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except OSError:
                pass
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=1)
    except KeyboardInterrupt:
        interrupted = True
        _terminate(proc, cleanup_scope)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=1)

    t_out.join(timeout=1)
    t_err.join(timeout=1)

    elapsed = time.monotonic_ns() - started
    stdout = stdout_sink[0] if stdout_sink else b""
    stderr = stderr_sink[0] if stderr_sink else b""
    stdout_truncated = bool(stdout_trunc and stdout_trunc[0])
    stderr_truncated = bool(stderr_trunc and stderr_trunc[0])

    if interrupted:
        status = "interrupted"
        detail = "interrupted"
    elif timed_out or proc.returncode is None:
        status = "timeout"
        detail = f"no exit within {timeout}s"
    elif proc.returncode < 0 and sys.platform != "win32":
        status = "signaled"
        detail = f"signal {-proc.returncode}"
    else:
        status = "exited"
        detail = "" if proc.returncode == 0 else f"exit {proc.returncode}"

    return ProcessOutcome(
        argv=argv,
        outcome=status,
        kind=status,
        returncode=proc.returncode,
        exit_code=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_bytes=stdout,
        stderr_bytes=stderr,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        elapsed_ns=elapsed,
        cleanup_scope=cleanup_scope,
        detail=detail,
    )


# Aliases for callers/tests that use a different spelling.
run_command = run
execute = run
