"""dynamic side-effect profiling in a child process."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_INTERPRETER = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _error_profile(module: str, error: str, duration_ms: float = 0) -> dict:
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


def _probe_module(module: str, python: str, timeout: float) -> dict:
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


def probe(
    modules: list[str],
    *,
    python: str | None = None,
    timeout: float = 30.0,
    refresh: bool = False,
) -> list[dict]:
    """Probe each module in a child process. Nothing is cached.

    The host never imports the target: the module name travels as a plain
    string and only the child imports it. `refresh` is accepted for
    compatibility and ignored.
    """
    exe = python or sys.executable
    results = []

    for module in modules:
        results.append(_probe_module(module, exe, timeout))

    return results
