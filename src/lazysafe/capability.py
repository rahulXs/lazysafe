"""decide whether an interpreter actually defers imports.

A successful launch proves nothing: CPython 3.14 accepts `-X lazy_imports=all`
and then imports eagerly anyway, so lazysafe asks the interpreter to import
something and checks whether it really stayed unloaded.
"""

import functools
import subprocess

_TIMEOUT_S = 30

# in a bare -c process json is not already loaded, so "import json" leaving
# sys.modules untouched can only mean the import was deferred
_PROBE = "import json, sys; print('json' in sys.modules)"

NOT_CAPABLE = (
    "the selected interpreter does not defer imports: it accepted "
    "-X lazy_imports=all but imported eagerly. lazysafe needs python 3.15 "
    "or newer for native lazy imports."
)


@functools.cache
def lazy_support(python):
    """Return (ok, reason). ok is False whenever no comparison can be trusted."""
    try:
        run = subprocess.run(
            [python, "-X", "lazy_imports=all", "-c", _PROBE],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError:
        return False, f"interpreter not found: {python}"
    except subprocess.TimeoutExpired:
        return False, f"interpreter did not answer within {_TIMEOUT_S}s: {python}"
    except OSError as exc:
        return False, f"could not start {python}: {exc}"

    if run.returncode != 0:
        detail = run.stderr.strip().splitlines()[-1] if run.stderr.strip() else "no output"
        return False, f"{python} failed with -X lazy_imports=all: {detail}"

    if run.stdout.strip() != "False":
        return False, NOT_CAPABLE

    return True, ""
