"""probe child process - runs in subprocess to capture side effects."""

import atexit
import contextlib
import importlib
import json
import os
import signal
import sys
import threading
import warnings

_INTERPRETER = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _snapshot():
    modules = set(sys.modules)
    threads = {(t.name, t.ident) for t in threading.enumerate()}
    atexit_count = len(atexit._exitfuncs) if hasattr(atexit, "_exitfuncs") else 0
    signal_handlers = {}
    for sig in signal.Signals:
        try:
            handler = signal.getsignal(sig)
            signal_handlers[sig.name] = repr(handler)
        except (OSError, ValueError):
            pass
    warnings_filters = list(warnings.filters)
    sys_path = set(sys.path)
    env_keys = set(os.environ)
    cwd = os.getcwd()
    umask = os.umask(0o022)
    os.umask(umask)

    fd_count = None
    with contextlib.suppress(OSError, FileNotFoundError):
        fd_count = len(os.listdir("/proc/self/fd"))

    return {
        "modules": sorted(modules),
        "threads": sorted(threads),
        "atexit_count": atexit_count,
        "signal_handlers": signal_handlers,
        "warnings_filters": len(warnings_filters),
        "sys_path": sorted(sys_path),
        "env_keys": sorted(env_keys),
        "cwd": cwd,
        "umask": oct(umask),
        "fd_count": fd_count,
    }


def _diff_snapshots(pre, post):
    effects = []

    new_mods = sorted(set(post["modules"]) - set(pre["modules"]))

    new_threads = set(post["threads"]) - set(pre["threads"])
    if new_threads:
        effects.append({"kind": "thread_spawned", "count": len(new_threads)})

    if post["atexit_count"] > pre["atexit_count"]:
        effects.append({
            "kind": "atexit_registered",
            "count": post["atexit_count"] - pre["atexit_count"],
        })

    for sig_name, post_val in post["signal_handlers"].items():
        pre_val = pre["signal_handlers"].get(sig_name)
        if pre_val is not None and pre_val != post_val:
            effects.append({"kind": "signal_handler_changed", "signal": sig_name})

    added_path = sorted(set(post["sys_path"]) - set(pre["sys_path"]))
    if added_path:
        effects.append({"kind": "sys_path_added", "paths": added_path})

    added_env = sorted(set(post["env_keys"]) - set(pre["env_keys"]))
    removed_env = sorted(set(pre["env_keys"]) - set(post["env_keys"]))
    if added_env or removed_env:
        effects.append({
            "kind": "env_changed",
            "added": added_env,
            "removed": removed_env,
        })

    if post["cwd"] != pre["cwd"]:
        effects.append({"kind": "cwd_changed", "from": pre["cwd"], "to": post["cwd"]})

    pre_fd = pre.get("fd_count")
    post_fd = post.get("fd_count")
    if pre_fd is not None and post_fd is not None and post_fd > pre_fd + 2:
        effects.append({
            "kind": "fds_opened",
            "count": post_fd - pre_fd,
        })

    if post["warnings_filters"] != pre["warnings_filters"]:
        effects.append({
            "kind": "warnings_filter_changed",
            "count": post["warnings_filters"] - pre["warnings_filters"],
        })

    return effects, new_mods


def _classify_verdict(effects):
    if not effects:
        return "safe"

    unsafe_kinds = {"thread_spawned", "signal_handler_changed", "sys_path_added"}
    for e in effects:
        if e["kind"] in unsafe_kinds:
            return "unsafe"

    return "risky"


def run(module_name, out_path):
    pre = _snapshot()

    try:
        importlib.import_module(module_name)
        error = None
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    post = _snapshot()
    effects, new_mods = _diff_snapshots(pre, post)

    verdict = _classify_verdict(effects)
    if error:
        verdict = "error"

    result = {
        "schema_version": 1,
        "module": module_name,
        "interpreter": _INTERPRETER,
        "imports_transitively": new_mods,
        "side_effects": effects,
        "verdict": verdict,
        "duration_ms": 0,
    }

    if error:
        result["error"] = error

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("usage: python -m lazysafe._probe_child MODULE OUT_PATH\n")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
