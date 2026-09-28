"""tests for import-profile timing measurement."""

import pytest

import lazysafe.measure as measure_module
from lazysafe.measure import (
    _parse_importtime_line,
    measure,
    result_to_dict,
)


def test_parse_importtime_line():
    """test parsing of importtime output lines."""
    line = "import time:       2 |          2 | _frozen_importlib"
    result = _parse_importtime_line(line)
    assert result == (2, 2, "_frozen_importlib")


def test_parse_importtime_line_cumulative():
    """test parsing with different cumulative/self values."""
    line = "import time:      22 |        150 | json"
    result = _parse_importtime_line(line)
    assert result == (150, 22, "json")


def test_parse_importtime_line_non_import():
    """test that non-importtime lines return None."""
    result = _parse_importtime_line("some other output")
    assert result is None


def test_parse_importtime_line_empty():
    """test that empty lines return None."""
    result = _parse_importtime_line("")
    assert result is None


def test_measure_runs_successfully():
    """test that measure runs and returns valid result."""
    result = measure(["json"], runs=2, warmup=1)
    assert result.entry_command == ["json"]
    assert result.ok is True
    assert result.errors == []
    assert result.runs == {"warmup": 1, "measured": 2, "succeeded": 3, "failed": 0}
    assert result.total_ms["p50"] > 0
    assert result.total_ms["min"] > 0
    assert result.total_ms["max"] >= result.total_ms["min"]


def test_measure_budget_rejected():
    """test that any budget request is rejected as unavailable."""
    with pytest.raises(ValueError, match="budget gating is unavailable"):
        measure(["json"], runs=2, warmup=1, budget_ms=999999)


def test_measure_budget_rejected_even_when_wide():
    """test that a generous budget cannot produce a passing decision."""
    with pytest.raises(ValueError, match="budget gating is unavailable"):
        measure(["json"], runs=2, warmup=1, budget_ms=0.001)


def test_measure_sleep_has_no_budget_decision():
    """test that the 250ms sleep case cannot yield a startup-budget verdict."""
    with pytest.raises(ValueError, match="budget gating is unavailable"):
        measure(["-c", "import time; time.sleep(0.25)"], runs=1, warmup=0, budget_ms=100)


def test_measure_sleep_without_budget_reports_import_profile():
    """test that the sleep case stays successful but carries no budget."""
    result = measure(["-c", "import time; time.sleep(0.25)"], runs=1, warmup=0)
    assert result.ok is True
    assert result.budget is None


def test_measure_has_module_timings():
    """test that per-module timings are captured."""
    result = measure(["json"], runs=2, warmup=1)
    assert len(result.per_module_top) > 0
    assert result.per_module_top[0].cumulative_us > 0


def test_result_to_dict():
    """test JSON serialization of MeasureResult."""
    result = measure(["json"], runs=2, warmup=1)
    d = result_to_dict(result)
    assert d["entry_command"] == ["json"]
    assert d["metric"] == "import_profile_max_cumulative_ms"
    assert d["ok"] is True
    assert d["errors"] == []
    assert d["budget"] is None
    assert len(d["per_module_top"]) > 0


def test_result_to_dict_all_failed():
    """test JSON serialization reports the failure instead of zero timings."""
    result = measure(["nonexistent_module_xyz"], runs=1, warmup=0)
    assert result.ok is False
    d = result_to_dict(result)
    assert d["ok"] is False
    assert d["total_ms"] is None
    assert len(d["errors"]) == 1
    assert d["errors"][0]["kind"] == "nonzero_exit"


def test_measure_invalid_runs():
    """test that runs=0 raises ValueError."""
    with pytest.raises(ValueError, match="runs must be >= 1"):
        measure(["json"], runs=0, warmup=1)


def test_measure_invalid_warmup():
    """test that warmup=-1 raises ValueError."""
    with pytest.raises(ValueError, match="warmup must be >= 0"):
        measure(["json"], runs=2, warmup=-1)


def test_measure_nonzero_exit_is_error():
    """test that a failing command is an execution error, not a zero timing."""
    result = measure(["nonexistent_module_xyz"], runs=2, warmup=1)
    assert result.ok is False
    assert result.total_ms is None
    assert result.per_module_top == []
    assert result.runs["succeeded"] == 0
    assert result.runs["failed"] == 3
    assert {e.kind for e in result.errors} == {"nonzero_exit"}
    assert all("exit" in e.detail for e in result.errors)


def test_measure_missing_executable_is_error():
    """test that a missing interpreter is a spawn error for every sample."""
    result = measure(["json"], runs=2, warmup=0, python="/nonexistent-python-xyz")
    assert result.ok is False
    assert result.total_ms is None
    assert result.runs == {"warmup": 0, "measured": 2, "succeeded": 0, "failed": 2}
    assert {e.kind for e in result.errors} == {"spawn_error"}


def test_measure_timeout_is_error(monkeypatch):
    """test that a hung command is a timeout error, not a timing."""
    monkeypatch.setattr(measure_module, "_SAMPLE_TIMEOUT_S", 1)
    result = measure(["-c", "import time; time.sleep(5)"], runs=1, warmup=0)
    assert result.ok is False
    assert result.total_ms is None
    assert [e.kind for e in result.errors] == ["timeout"]


def test_measure_mixed_success_cannot_pass(tmp_path, monkeypatch):
    """test that one failed sample poisons the run even if others succeed."""
    script = tmp_path / "flaky_first.py"
    script.write_bytes(
        b"import pathlib, sys\n"
        b"marker = pathlib.Path(sys.argv[1])\n"
        b"if marker.exists():\n"
        b"    sys.exit(0)\n"
        b"marker.touch()\n"
        b"sys.exit(1)\n"
    )
    marker = tmp_path / "marker"
    monkeypatch.chdir(tmp_path)

    result = measure([str(script), str(marker)], runs=2, warmup=0)

    assert result.ok is False
    assert result.total_ms is None
    assert result.budget is None
    assert result.runs["succeeded"] == 1
    assert result.runs["failed"] == 1
    assert [e.kind for e in result.errors] == ["nonzero_exit"]
    assert result.errors[0].phase == "measured"
