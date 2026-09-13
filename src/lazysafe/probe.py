"""dynamic side-effect profiling via subprocess sandbox."""

import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_INTERPRETER = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _get_cache_dir() -> Path:
    return Path(".lazysafe/cache/profiles")


def _get_cache_key(module: str, python: str) -> str:
    interpreter = subprocess.run(
        [python, "-c", "import sys; print(sys.version)"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    try:
        spec = __import__("importlib").util.find_spec(module)
        mtime = Path(spec.origin).stat().st_mtime if spec and spec.origin else 0
    except (ModuleNotFoundError, AttributeError, OSError):
        mtime = 0

    raw = f"{module}:{interpreter}:{mtime}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


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
    exe = python or sys.executable
    cache_dir = _get_cache_dir()
    results = []

    for module in modules:
        cache_key = _get_cache_key(module, exe)
        cache_path = cache_dir / f"{cache_key}.json"

        if not refresh and cache_path.exists():
            try:
                profile = json.loads(cache_path.read_text())
                results.append(profile)
                continue
            except (json.JSONDecodeError, OSError):
                pass

        profile = _probe_module(module, exe, timeout)

        cache_dir.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            cache_path.write_text(json.dumps(profile, indent=2))

        results.append(profile)

    return results
