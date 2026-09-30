"""dynamic side-effect profiling in a child process."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_INTERPRETER = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _error_profile(module, error, duration_ms=0):
    return {
        "schema_version": 1,
        "module": module,
        "interpreter": _INTERPRETER,
        "imports_transitively": [],
        "side_effects": [],
        "verdict": "error",
        "duration_ms": duration_ms,
        "error": error,
    }


def _probe_module(module, python, timeout):
    out_path = Path(tempfile.gettempdir()) / f"lazysafe_probe_{module.replace('.', '_')}.json"
    out_posix = out_path.as_posix()
    child_script = (
        f"from lazysafe._probe_child import run; "
        f"run('{module}', '{out_posix}')"
    )

    src_dir = str(Path(__file__).parent.parent)
    path_dirs = [src_dir] + [p for p in sys.path if p and Path(p).is_dir()]

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env["PYTHONPATH"] = os.pathsep.join(path_dirs)

    start = time.monotonic()
    try:
        result = subprocess.run(
            [python, "-c", child_script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        duration_ms = (time.monotonic() - start) * 1000
    except subprocess.TimeoutExpired:
        return _error_profile(
            module, f"probe timed out after {timeout}s", timeout * 1000
        )
    except FileNotFoundError:
        return _error_profile(module, f"python not found: {python}")

    if out_path.exists():
        try:
            profile = json.loads(out_path.read_text())
            profile["duration_ms"] = round(duration_ms, 1)
            out_path.unlink(missing_ok=True)
            return profile
        except (json.JSONDecodeError, OSError):
            pass

    stderr_msg = result.stderr[:500] if result.stderr else "unknown error"
    return _error_profile(module, stderr_msg, round(duration_ms, 1))


def probe(modules, *, python=None, timeout=30.0, refresh=False):
    """Import each module in a child process and record what it changed.

    The host never imports the target. Results are never cached, so `refresh`
    is accepted and ignored.
    """
    exe = python or sys.executable
    results = []

    for module in modules:
        results.append(_probe_module(module, exe, timeout))

    return results
