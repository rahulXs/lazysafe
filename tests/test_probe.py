"""tests for probe and _probe_child."""

import json
import os
import sys
import tempfile
from pathlib import Path

from lazysafe._probe_child import _classify_verdict, _diff_snapshots, _snapshot, run
from lazysafe.probe import _get_cache_dir, probe

FIXTURES = Path(__file__).parent / "fixtures" / "probe_pkg"
OWN_PREFIX = "tests.fixtures.probe_pkg."


class TestSnapshot:
    def test_returns_expected_keys(self):
        snap = _snapshot()
        assert "modules" in snap
        assert "threads" in snap
        assert "sys_path" in snap
        assert "env_keys" in snap

    def test_modules_are_sorted(self):
        snap = _snapshot()
        assert snap["modules"] == sorted(snap["modules"])


class TestDiffSnapshots:
    def test_no_changes(self):
        pre = _snapshot()
        post = _snapshot()
        effects, new_mods = _diff_snapshots(pre, post)
        assert effects == []
        assert new_mods == []

    def test_new_modules_detected(self):
        pre = _snapshot()
        import xmlrpc.client  # noqa: F401
        post = _snapshot()
        _, new_mods = _diff_snapshots(pre, post)
        assert "xmlrpc.client" in new_mods

    def test_sys_path_added(self):
        pre = _snapshot()
        sys.path.append("/tmp/test_path_xyz")
        post = _snapshot()
        effects, _ = _diff_snapshots(pre, post)
        sys.path.pop()
        path_effects = [e for e in effects if e["kind"] == "sys_path_added"]
        assert len(path_effects) == 1
        assert "/tmp/test_path_xyz" in path_effects[0]["paths"]


class TestClassifyVerdict:
    def test_empty_is_safe(self):
        assert _classify_verdict([]) == "safe"

    def test_thread_is_unsafe(self):
        assert _classify_verdict([{"kind": "thread_spawned", "count": 1}]) == "unsafe"

    def test_signal_is_unsafe(self):
        effect = {"kind": "signal_handler_changed", "signal": "SIGTERM"}
        assert _classify_verdict([effect]) == "unsafe"

    def test_syspath_is_unsafe(self):
        assert _classify_verdict([{"kind": "sys_path_added", "paths": ["/opt"]}]) == "unsafe"

    def test_warnings_only_is_risky(self):
        assert _classify_verdict([{"kind": "warnings_filter_changed", "count": 1}]) == "risky"

    def test_atexit_only_is_risky(self):
        assert _classify_verdict([{"kind": "atexit_registered", "count": 1}]) == "risky"


class TestProbeChildRun:
    def test_writes_json_output(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            run("json", out_path)
            result = json.loads(Path(out_path).read_text())
            assert result["module"] == "json"
            assert result["verdict"] in ("safe", "risky", "unsafe", "error")
            assert "schema_version" in result
        finally:
            os.unlink(out_path)

    def test_crash_gives_error_verdict(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            sys.path.insert(0, str(FIXTURES))
            run(f"{OWN_PREFIX}crasher", out_path)
            result = json.loads(Path(out_path).read_text())
            assert result["verdict"] == "error"
            assert "RuntimeError" in result["error"]
        finally:
            sys.path.pop(0)
            os.unlink(out_path)


class TestProbe:
    def test_pure_module_safe(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            results = probe([f"{OWN_PREFIX}pure"])
            assert len(results) == 1
            assert results[0]["verdict"] == "safe"
            assert results[0]["module"] == f"{OWN_PREFIX}pure"
        finally:
            sys.path.pop(0)

    def test_thread_spawner_unsafe(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            results = probe([f"{OWN_PREFIX}thread_spawner"])
            assert len(results) == 1
            assert results[0]["verdict"] == "unsafe"
            kinds = [e["kind"] for e in results[0]["side_effects"]]
            assert "thread_spawned" in kinds
        finally:
            sys.path.pop(0)

    def test_syspath_adder_unsafe(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            results = probe([f"{OWN_PREFIX}syspath_adder"])
            assert len(results) == 1
            assert results[0]["verdict"] == "unsafe"
            kinds = [e["kind"] for e in results[0]["side_effects"]]
            assert "sys_path_added" in kinds
        finally:
            sys.path.pop(0)

    def test_crash_gives_error(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            results = probe([f"{OWN_PREFIX}crasher"])
            assert len(results) == 1
            assert results[0]["verdict"] == "error"
            assert "error" in results[0]
        finally:
            sys.path.pop(0)

    def test_multiple_modules(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            results = probe([f"{OWN_PREFIX}pure", f"{OWN_PREFIX}thread_spawner"])
            assert len(results) == 2
            verdicts = {r["module"]: r["verdict"] for r in results}
            assert verdicts[f"{OWN_PREFIX}pure"] == "safe"
            assert verdicts[f"{OWN_PREFIX}thread_spawner"] == "unsafe"
        finally:
            sys.path.pop(0)

    def test_cache_hit_avoids_subprocess(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            probe([f"{OWN_PREFIX}pure"])
            cache_dir = _get_cache_dir()
            assert any(cache_dir.glob("*.json"))
        finally:
            sys.path.pop(0)
