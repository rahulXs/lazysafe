"""tests for startup timing measurement."""


from lazysafe.measure import (
    MeasureResult,
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
    assert isinstance(result, MeasureResult)
    assert result.entry_command == ["json"]
    assert result.runs == {"warmup": 1, "measured": 2}
    assert result.total_ms["p50"] > 0
    assert result.total_ms["min"] > 0
    assert result.total_ms["max"] >= result.total_ms["min"]


def test_measure_with_budget_pass():
    """test budget gate passes when within budget."""
    result = measure(["json"], runs=2, warmup=1, budget_ms=999999)
    assert result.budget is not None
    assert result.budget["passed"] is True


def test_measure_with_budget_fail():
    """test budget gate fails when exceeded."""
    result = measure(["json"], runs=2, warmup=1, budget_ms=0.001)
    assert result.budget is not None
    assert result.budget["passed"] is False


def test_measure_has_module_timings():
    """test that per-module timings are captured."""
    result = measure(["json"], runs=2, warmup=1)
    assert len(result.per_module_top) > 0
    assert result.per_module_top[0].module is not None
    assert result.per_module_top[0].cumulative_us > 0


def test_result_to_dict():
    """test JSON serialization of MeasureResult."""
    result = measure(["json"], runs=2, warmup=1)
    d = result_to_dict(result)
    assert d["schema_version"] == 1
    assert d["entry_command"] == ["json"]
    assert "p50" in d["total_ms"]
    assert "min" in d["total_ms"]
    assert "max" in d["total_ms"]
    assert "stdev" in d["total_ms"]
    assert isinstance(d["per_module_top"], list)


def test_result_to_dict_with_budget():
    """test JSON serialization includes budget info."""
    result = measure(["json"], runs=2, warmup=1, budget_ms=500)
    d = result_to_dict(result)
    assert d["budget"] is not None
    assert "limit_ms" in d["budget"]
    assert "passed" in d["budget"]
