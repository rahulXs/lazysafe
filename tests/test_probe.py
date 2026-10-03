"""tests for probe and _probe_child."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from lazysafe._probe_child import _classify_verdict, _diff_snapshots, _snapshot, run
from lazysafe.probe import probe

FIXTURES = Path(__file__).parent / "fixtures" / "probe_pkg"
OWN_PREFIX = "tests.fixtures.probe_pkg."


@pytest.fixture
def probe_importable():
    """Put the probe fixtures on sys.path, as a user project would be."""
    sys.path.insert(0, str(FIXTURES))
    yield
    sys.path.pop(0)


def test_diff_reports_nothing_when_nothing_changed():
    effects, new_mods = _diff_snapshots(_snapshot(), _snapshot())
    assert effects == []
    assert new_mods == []


def test_diff_reports_newly_imported_modules():
    pre = _snapshot()
    import xmlrpc.client  # noqa: F401

    _, new_mods = _diff_snapshots(pre, _snapshot())
    assert "xmlrpc.client" in new_mods


def test_diff_reports_added_sys_path_entry():
    pre = _snapshot()
    sys.path.append("/tmp/test_path_xyz")
    try:
        effects, _ = _diff_snapshots(pre, _snapshot())
    finally:
        sys.path.pop()

    added = [e for e in effects if e["kind"] == "sys_path_added"]
    assert len(added) == 1
    assert "/tmp/test_path_xyz" in added[0]["paths"]


@pytest.mark.parametrize(
    ("effects", "expected"),
    [
        ([], "safe"),
        ([{"kind": "thread_spawned", "count": 1}], "unsafe"),
        ([{"kind": "sys_path_added", "paths": ["/opt"]}], "unsafe"),
        ([{"kind": "signal_handler_changed", "signal": "SIGTERM"}], "unsafe"),
        ([{"kind": "atexit_registered", "count": 1}], "risky"),
        ([{"kind": "warnings_filter_changed", "count": 1}], "risky"),
    ],
)
def test_verdict_separates_blocking_effects_from_merely_noteworthy(effects, expected):
    # only thread/path/signal changes block a lazy rewrite; the rest are notes
    assert _classify_verdict(effects) == expected


def test_child_run_writes_a_profile(probe_importable):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out_path = f.name
    try:
        run("json", out_path)
        result = json.loads(Path(out_path).read_text())
        assert result["module"] == "json"
    finally:
        os.unlink(out_path)


@pytest.mark.parametrize(
    ("module", "verdict"),
    [
        (f"{OWN_PREFIX}pure", "safe"),
        (f"{OWN_PREFIX}thread_spawner", "unsafe"),
        (f"{OWN_PREFIX}syspath_adder", "unsafe"),
        (f"{OWN_PREFIX}crasher", "error"),
    ],
)
def test_probe_reports_each_fixture_verdict(probe_importable, module, verdict):
    results = probe([module])
    assert len(results) == 1
    assert results[0]["module"] == module
    assert results[0]["verdict"] == verdict


def test_probe_handles_several_modules(probe_importable):
    results = probe([f"{OWN_PREFIX}pure", f"{OWN_PREFIX}thread_spawner"])
    assert {r["module"]: r["verdict"] for r in results} == {
        f"{OWN_PREFIX}pure": "safe",
        f"{OWN_PREFIX}thread_spawner": "unsafe",
    }


def test_probe_writes_no_cache(tmp_path, monkeypatch, probe_importable):
    monkeypatch.chdir(tmp_path)
    probe([f"{OWN_PREFIX}pure"])
    assert not (tmp_path / ".lazysafe").exists()


def test_dotted_target_never_runs_in_the_host(tmp_path, monkeypatch):
    # the parent package writes its own PID on import; only the child may do that
    pkg = tmp_path / "hostiso_parent"
    pkg.mkdir()
    (pkg / "__init__.py").write_bytes(
        b"import os\n"
        b"from pathlib import Path\n"
        b'Path("host-import-pid.txt").write_text(str(os.getpid()))\n'
    )
    (pkg / "child.py").write_bytes(b"VALUE = 1\n")
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        results = probe(["hostiso_parent.child"], timeout=30)
        assert "hostiso_parent" not in sys.modules
        marker = tmp_path / "host-import-pid.txt"
        assert marker.exists()
        assert int(marker.read_text().strip()) != os.getpid()
        assert results[0]["module"] == "hostiso_parent.child"
    finally:
        sys.path.pop(0)
        sys.modules.pop("hostiso_parent", None)
        sys.modules.pop("hostiso_parent.child", None)
