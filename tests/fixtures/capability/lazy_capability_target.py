"""Import-time effect used to observe whether an import actually executed.

Plain syntax so the fixture stays parseable on every supported host. The
marker path is written once per import so a test can distinguish "never
executed" from "executed at least once".
"""

import os

_MARKER_ENV = "LAZYSAFE_CAPABILITY_MARKER"

with open(os.environ[_MARKER_ENV], "a", encoding="utf-8") as _handle:
    _handle.write("imported\n")

VALUE = "target-loaded"
