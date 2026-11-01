"""tests for command-duration measurement."""

import sys

from lazysafe.measure import measure, result_to_dict

PY = sys.executable


def test_measure_runs_successfully():
    result = measure([PY, "-c", "import json"], runs=2, warmup=1)
    assert result.ok is True
    assert result.runs["warmup"] == 1
    assert result.runs["measured"] == 2
    assert result.total_ms is not None
    assert result.total_ms["p50"] > 0


def test_measure_failed_sample_invalidates_summary():
    result = measure([PY, "-c", "raise SystemExit(1)"], runs=1, warmup=0)
    assert result.ok is False
    assert result.total_ms is None


def test_result_to_dict():
    result = measure([PY, "-c", "import json"], runs=2, warmup=1)
    d = result_to_dict(result)
    assert d["schema_version"] == 2
    assert d["kind"] == "measurement"
    assert d["result"]["runs"]["measured"] == 2
