"""tests for scan coverage: missing, unreadable, and unparseable sources."""

import os

import pytest

from lazysafe.cli import _read_source_for_analysis
from lazysafe.discovery import scan_directory
from lazysafe.model import Classification, ModuleNode, Origin
from lazysafe.static.classify import _classify_module, classify_all


def _write(root, name, content: bytes):
    path = root / name
    path.write_bytes(content)
    return path


def test_missing_target_is_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = scan_directory(["does-not-exist"], tmp_path)
    assert model.modules == []
    assert model.skipped == [{"path": "does-not-exist", "reason": "not-found"}]


def test_file_target_is_skipped(tmp_path, monkeypatch):
    _write(tmp_path, "one.py", b"VALUE = 1\n")
    monkeypatch.chdir(tmp_path)
    model = scan_directory(["one.py"], tmp_path)
    assert model.modules == []
    assert model.skipped == [{"path": "one.py", "reason": "not-a-directory"}]


def test_invalid_syntax_is_skipped_but_good_file_scans(tmp_path, monkeypatch):
    _write(tmp_path, "good.py", b"VALUE = 1\n")
    _write(tmp_path, "broken.py", b"def broken(:\n")
    monkeypatch.chdir(tmp_path)
    model = scan_directory(["."], tmp_path)
    assert [m.module for m in model.modules] == ["good"]
    assert len(model.skipped) == 1
    assert model.skipped[0]["path"] == "broken.py"


def test_unreadable_file_is_skipped(tmp_path, monkeypatch):
    _write(tmp_path, "good.py", b"VALUE = 1\n")
    target = _write(tmp_path, "noread.py", b"VALUE = 1\n")
    target.chmod(0o000)
    if os.access(target, os.R_OK):
        pytest.skip("platform still allows reading the file")
    monkeypatch.chdir(tmp_path)
    try:
        model = scan_directory(["."], tmp_path)
    finally:
        target.chmod(0o644)
    assert [m.module for m in model.modules] == ["good"]
    assert [s["path"] for s in model.skipped] == ["noread.py"]


def test_empty_directory_scans_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = scan_directory(["."], tmp_path)
    assert model.modules == []
    assert model.skipped == []


def test_coverage_gap_classifies_unknown():
    node = ModuleNode("pkg.mod", "pkg/mod.py", Origin.OWN)
    node.coverage_gaps.append("source unreadable during analysis")
    assert _classify_module(node) == Classification.UNKNOWN


def test_unreadable_during_analysis_becomes_unknown(tmp_path, monkeypatch):
    _write(tmp_path, "good.py", b"VALUE = 1\n")
    monkeypatch.chdir(tmp_path)
    model = scan_directory(["."], tmp_path)
    assert len(model.modules) == 1
    node = model.modules[0]
    (tmp_path / "good.py").unlink()
    assert _read_source_for_analysis(node, model) is None
    classify_all(model)
    assert node.classification == Classification.UNKNOWN
    assert model.skipped == [{"path": "good.py", "reason": "unreadable"}]
