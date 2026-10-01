"""tests for verify: an unsuccessful or unsupported run is never a pass."""

import sys

import pytest

from lazysafe.capability import lazy_support
from lazysafe.cli import main
from lazysafe.verify import verify

CAPABLE = lazy_support(sys.executable)[0]

needs_native = pytest.mark.skipif(
    not CAPABLE, reason="host interpreter does not defer imports"
)


def _verify_cli(*argv):
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", *argv])
    return exc_info.value.code


def test_capability_check_rejects_a_non_defining_interpreter():
    # 3.14 accepts -X lazy_imports=all and still imports eagerly (LS-02)
    ok, reason = lazy_support("/usr/bin/python3.14")
    if ok:
        pytest.skip("python3.14 on this host defers imports, which is unexpected")
    assert "does not defer imports" in reason


def test_capability_check_rejects_a_missing_interpreter():
    ok, reason = lazy_support("/nonexistent/python-xyz")
    assert ok is False
    assert "not found" in reason


@needs_native
def test_two_equal_failures_are_not_equivalent():
    # the LS-01 reproduction: two runs that both exit 7 used to compare equal
    result = verify(["-c", "raise SystemExit(7)"])
    assert result.equivalent is False
    assert result.error
    assert "exited 7" in result.error


@needs_native
def test_missing_interpreter_is_not_equivalent():
    result = verify(["-c", "pass"], python="/nonexistent/python-xyz")
    assert result.equivalent is False
    assert "not found" in result.error


def test_incapable_interpreter_is_rejected_before_running_anything():
    # the command would succeed eagerly; it must not be claimed as verified
    result = verify(["-c", "pass"], lazy_python="/usr/bin/python3.14")
    if result.equivalent:
        pytest.skip("python3.14 on this host defers imports, which is unexpected")
    assert "does not defer imports" in result.error
    assert result.eager.exit_code is None
    assert result.lazy.exit_code is None


@needs_native
def test_timeout_is_an_error_not_a_comparison():
    result = verify(["-c", "import time; time.sleep(600)"], timeout=1)
    assert result.equivalent is False
    assert "timed out" in result.error


@needs_native
def test_different_temporary_paths_stay_different():
    # exact comparison only. these two paths used to normalize to the same text
    result = verify([
        "-c",
        "import os, tempfile; "
        "print(os.path.join(tempfile.gettempdir(), 'a' + os.urandom(4).hex()))",
    ])
    assert result.equivalent is False
    assert "stdout differs" in result.diffs


@needs_native
def test_matching_output_is_equivalent():
    result = verify(["-c", "print('hello')"])
    assert result.equivalent is True
    assert result.error == ""
    assert result.eager.exit_code == 0
    assert result.lazy.exit_code == 0


@needs_native
def test_readme_style_duplicated_interpreter_fails():
    # `-- python -c ...` asks lazysafe to run a file named "python"
    code = _verify_cli("--", sys.executable, "-c", "print('hello')")
    assert code == 2


@needs_native
def test_cli_exits_two_on_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--", "-c", "raise SystemExit(3)"])
    assert exc_info.value.code == 2
    assert "exited 3" in capsys.readouterr().err


@needs_native
def test_cli_labels_the_operation_as_not_a_source_edit_check(capsys):
    main(["verify", "--", "-c", "print('hello')"])
    out = capsys.readouterr().out
    assert "does not check a source edit" in out
    assert "EQUIVALENT" in out
