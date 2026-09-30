"""tests for verify."""

import sys

from lazysafe.verify import _normalize, _run_command, verify


def test_default_normalization_hides_real_differences():
    # documented as a known over-normalization (LS-02): two different temp
    # paths and two different durations both collapse to the same text, so an
    # exact comparison is not what verify actually performs
    assert _normalize("wrote /tmp/result-a") == _normalize("wrote /tmp/result-b")
    assert _normalize("took 10.5ms") == _normalize("took 99.5ms")


def test_run_command_reports_a_timeout_distinctly():
    result = _run_command(["-c", "import time; time.sleep(600)"], sys.executable, timeout=1)
    assert result.exit_code == -1


def test_verify_compares_exit_codes_and_output():
    result = verify(["-c", "print('hello')"], python=sys.executable)
    assert result.equivalent is True
    assert result.eager.exit_code == 0
    assert result.lazy.exit_code == 0
