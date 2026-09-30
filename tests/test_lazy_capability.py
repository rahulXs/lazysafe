"""Qualify observed PEP 810 lazy-import behavior on a real interpreter.

Capability is proven by deferred execution, not by a version string or a clean
launch: 3.14 accepts -X lazy_imports=all and still imports eagerly (LS-02).

The child program goes in a string because `lazy import` is 3.15 grammar and
this repo lints against 3.11.
"""

import functools
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_TARGET = "lazy_capability_target"
_MARKER_ENV = "LAZYSAFE_CAPABILITY_MARKER"
_REQUIRE_ENV = "LAZYSAFE_REQUIRE_NATIVE_LAZY"
_CHILD_TIMEOUT_S = 60
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "capability"

_DEFERRED_PROGRAM = f"""\
import os
import sys

lazy import {_TARGET}

print("bound", "{_TARGET}" in globals())
print("loaded_before_use", "{_TARGET}" in sys.modules)
print("executed_before_use", os.path.exists(os.environ["LAZYSAFE_CAPABILITY_MARKER"]))
{_TARGET}.VALUE
print("loaded_after_use", "{_TARGET}" in sys.modules)
"""

_EAGER_PROGRAM = f"""\
import sys

import {_TARGET}

print("loaded_after_import", "{_TARGET}" in sys.modules)
"""

_IDENTITY_PROGRAM = """\
import sys

print("implementation", sys.implementation.name)
print("version_info", ".".join(str(part) for part in sys.version_info[:3]))
print("cache_tag", sys.implementation.cache_tag)
"""


def _run_child(python, program, mode, marker, cwd):
    args = [python, "-X", f"lazy_imports={mode}", "-c", program]
    env = {
        **os.environ,
        "PYTHONPATH": str(_FIXTURE_DIR),
        _MARKER_ENV: str(marker),
    }
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
        env=env,
        cwd=cwd,
        check=False,
    )


def _facts(stdout):
    parsed = {}
    for line in stdout.splitlines():
        key, _, value = line.partition(" ")
        if key:
            parsed[key] = value.strip()
    return parsed


def _marker_writes(marker):
    if not marker.exists():
        return []
    return [line for line in marker.read_text(encoding="utf-8").splitlines() if line]


@functools.cache
def _defers_explicit_lazy_import(python):
    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        marker = work / "marker.txt"
        try:
            run = _run_child(python, _DEFERRED_PROGRAM, "normal", marker, work)
        except subprocess.TimeoutExpired:
            return False
        if run.returncode != 0:
            return False
        facts = _facts(run.stdout)
        return (
            facts.get("bound") == "True"
            and facts.get("loaded_before_use") == "False"
            and facts.get("executed_before_use") == "False"
            and facts.get("loaded_after_use") == "True"
            and _marker_writes(marker) == ["imported"]
        )


def _build_id(python):
    try:
        run = subprocess.run(
            [python, "-c", _IDENTITY_PROGRAM],
            capture_output=True,
            text=True,
            timeout=_CHILD_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return python
    facts = _facts(run.stdout)
    name = facts.get("implementation", "?")
    version = facts.get("version_info", "?")
    tag = facts.get("cache_tag", "?")
    return f"{name} {version} [{tag}] ({python})"


@pytest.fixture(scope="module")
def native_python():
    # A local host without one reports a skip. The CI job sets
    # LAZYSAFE_REQUIRE_NATIVE_LAZY=1 so a missing interpreter fails instead.
    if _defers_explicit_lazy_import(sys.executable):
        return sys.executable
    reason = (
        f"{_build_id(sys.executable)} accepted the launch but did not defer an "
        "explicit lazy import; native lazy qualification did not run"
    )
    if os.environ.get(_REQUIRE_ENV) == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def test_explicit_lazy_import_defers_execution(native_python, tmp_path):
    marker = tmp_path / "marker.txt"
    run = _run_child(native_python, _DEFERRED_PROGRAM, "normal", marker, tmp_path)

    assert run.returncode == 0, run.stderr
    facts = _facts(run.stdout)
    assert facts["bound"] == "True"
    assert facts["loaded_before_use"] == "False"
    assert facts["executed_before_use"] == "False"


def test_first_use_executes_the_deferred_import(native_python, tmp_path):
    marker = tmp_path / "marker.txt"
    run = _run_child(native_python, _DEFERRED_PROGRAM, "normal", marker, tmp_path)

    assert run.returncode == 0, run.stderr
    assert _facts(run.stdout)["loaded_after_use"] == "True"
    assert _marker_writes(marker) == ["imported"]


def test_normal_import_executes_immediately(native_python, tmp_path):
    marker = tmp_path / "marker.txt"
    run = _run_child(native_python, _EAGER_PROGRAM, "normal", marker, tmp_path)

    assert run.returncode == 0, run.stderr
    assert _facts(run.stdout)["loaded_after_import"] == "True"
    assert _marker_writes(marker) == ["imported"]


# The two modes lazysafe relies on, with the evidence each one must show.
@pytest.mark.parametrize(
    ("mode", "loaded_after_plain_import", "expected_marker_writes"),
    [
        ("normal", "True", ["imported"]),
        ("all", "False", []),
    ],
)
def test_modes_lazysafe_uses_are_accepted_and_differ(
    native_python, tmp_path, mode, loaded_after_plain_import, expected_marker_writes
):
    marker = tmp_path / f"marker-{mode}.txt"
    run = _run_child(native_python, _EAGER_PROGRAM, mode, marker, tmp_path)

    assert run.returncode == 0, run.stderr
    assert _facts(run.stdout)["loaded_after_import"] == loaded_after_plain_import
    assert _marker_writes(marker) == expected_marker_writes


def test_qualified_interpreter_reports_its_build(native_python):
    run = subprocess.run(
        [native_python, "-c", _IDENTITY_PROGRAM],
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    facts = _facts(run.stdout)
    assert facts["implementation"] == "cpython"
    assert [part.isdigit() for part in facts["version_info"].split(".")] == [True] * 3
    assert facts["cache_tag"]
