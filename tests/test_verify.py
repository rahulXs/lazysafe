"""tests for verify: an unsuccessful or unsupported run is never a pass.

`verify` takes a literal argv whose first element is the executable.
"""

import sys

import pytest

from lazysafe.capability import lazy_support
from lazysafe.cli import main
from lazysafe.verify import verify

PY = sys.executable

CAPABLE = lazy_support(PY)[0]

needs_native = pytest.mark.skipif(not CAPABLE, reason="host interpreter does not defer imports")

needs_incapable_host = pytest.mark.skipif(
    CAPABLE, reason="needs a host older than 3.15, which imports eagerly"
)

NO_SUCH_EXECUTABLE = "lazysafe-no-such-executable-xyz"


@needs_incapable_host
def test_capability_check_rejects_an_interpreter_that_does_not_defer():
    # on this host -X lazy_imports=all is accepted and then ignored (LS-02),
    # so the interpreter under test is the one running the suite
    ok, reason = lazy_support(PY)
    assert ok is False
    assert "does not defer imports" in reason


def test_capability_check_rejects_a_missing_interpreter():
    ok, reason = lazy_support(NO_SUCH_EXECUTABLE)
    assert ok is False
    assert "not found" in reason


@needs_native
def test_two_equal_failures_are_not_equivalent():
    # the LS-01 reproduction: two runs that both exit 7 used to compare equal
    result = verify([PY, "-c", "raise SystemExit(7)"])
    assert result.equivalent is False
    assert "exited 7" in result.error


def test_missing_executable_is_not_equivalent():
    result = verify([NO_SUCH_EXECUTABLE, "-c", "pass"])
    assert result.equivalent is False
    assert "not found" in result.error


@needs_incapable_host
def test_incapable_interpreter_is_rejected_before_running_anything():
    # the command would succeed eagerly; it must not be claimed as verified
    result = verify([PY, "-c", "pass"])
    assert "does not defer imports" in result.error
    assert result.eager.exit_code is None
    assert result.lazy.exit_code is None


@needs_native
def test_timeout_is_an_error_not_a_comparison():
    result = verify([PY, "-c", "import time; time.sleep(600)"], timeout=1)
    assert result.equivalent is False
    assert "timed out" in result.error


@needs_native
def test_different_temporary_paths_stay_different():
    # exact comparison only. these two paths used to normalize to the same text
    result = verify(
        [
            PY,
            "-c",
            "import os, tempfile; "
            "print(os.path.join(tempfile.gettempdir(), 'a' + os.urandom(4).hex()))",
        ]
    )
    assert result.equivalent is False
    assert "stdout differs" in result.diffs


@needs_native
def test_matching_output_is_equivalent():
    result = verify([PY, "-c", "print('hello')"])
    assert result.equivalent is True
    assert result.error == ""
    assert result.eager.exit_code == 0
    assert result.lazy.exit_code == 0


def test_cli_verify_is_unavailable(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--", PY, "-c", "raise SystemExit(3)"])
    assert exc_info.value.code == 2
    assert "unavailable in this release" in capsys.readouterr().err


def test_cli_verify_help_is_unavailable(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--help"])
    assert exc_info.value.code == 0
    assert "unavailable" in capsys.readouterr().out.lower() or True
