"""decide whether an interpreter actually defers imports.

A successful launch proves nothing: CPython 3.14 accepts `-X lazy_imports=all`
and then imports eagerly anyway, so lazysafe asks the interpreter to import
something and checks whether it really stayed unloaded.
"""

import os

from lazysafe import process as process_runner

_TIMEOUT_S = 30

# in a bare -c process json is not already loaded, so "import json" leaving
# sys.modules untouched can only mean the import was deferred
_PROBE = "import json, sys; print('json' in sys.modules)"

NOT_CAPABLE = (
    "the selected interpreter does not defer imports: it accepted "
    "-X lazy_imports=all but imported eagerly. lazysafe needs python 3.15 "
    "or newer for native lazy imports."
)


def lazy_support(python, timeout=30.0):
    """Return (ok, reason). ok is False whenever no comparison can be trusted."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    outcome = process_runner.run(
        [python, "-X", "lazy_imports=all", "-c", _PROBE],
        timeout=min(timeout, _TIMEOUT_S),
        env=env,
        capture_limit=process_runner.DEFAULT_CAPTURE_LIMIT,
    )
    if outcome.outcome == "spawn_error":
        return False, f"interpreter not found: {python}"
    if outcome.outcome in ("timeout", "interrupted"):
        return False, f"interpreter did not answer within {_TIMEOUT_S}s: {python}"
    if outcome.outcome == "signaled":
        return False, f"could not start {python}: {outcome.detail}"
    run_returncode = outcome.returncode
    run_stdout = outcome.stdout.decode("utf-8", "replace")
    run_stderr = outcome.stderr.decode("utf-8", "replace")

    if run_returncode != 0:
        detail = run_stderr.strip().splitlines()[-1] if run_stderr.strip() else "no output"
        return False, f"{python} failed with -X lazy_imports=all: {detail}"

    if run_stdout.strip() != "False":
        return False, NOT_CAPABLE

    return True, ""
