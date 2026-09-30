"""tests for static analysis rules SE01-SE08."""

from pathlib import Path

import pytest

from lazysafe.discovery import scan_directory
from lazysafe.model import Classification, Origin
from lazysafe.static import run_static
from lazysafe.static.classify import _classify_module, classify_all

FIXTURES = Path(__file__).parent / "fixtures" / "sideeffect_pkg"


def _analyze_fixture(name):
    """Classify one fixture file and return its module node."""
    path = FIXTURES / f"{name}.py"
    source = path.read_text(encoding="utf-8")
    model = scan_directory(["tests/fixtures/sideeffect_pkg"], Path.cwd())
    for node in model.modules:
        if node.file.endswith(f"{name}.py"):
            node.findings = run_static(node, source)
            return node
    raise AssertionError(f"fixture {name} was not scanned")


@pytest.mark.parametrize(
    ("fixture", "rule"),
    [
        ("se01_call", "SE01"),
        ("se02_assign", "SE02"),
        ("se03_sys", "SE03"),
        ("se03_augassign", "SE02"),
        ("se04_register", "SE04"),
        ("se05_io", "SE05"),
        ("se06_decorators", "SE06"),
        ("se07_importlib", "SE07"),
        ("se08_tryexcept", "SE08"),
        ("se08_tuple_except", "SE08"),
    ],
)
def test_each_rule_fires_on_its_fixture(fixture, rule):
    node = _analyze_fixture(fixture)
    assert rule in {f.rule for f in node.findings}


def test_clean_package_is_safe():
    model = scan_directory(["tests/fixtures/clean_pkg"], Path.cwd())
    for node in model.modules:
        node.findings = run_static(node, Path(node.file).read_text(encoding="utf-8"))
    classify_all(model)

    own = [n for n in model.modules if n.origin == Origin.OWN]
    assert own
    assert all(n.classification == Classification.SAFE for n in own)


def test_side_effect_fixtures_land_in_risky_or_unsafe():
    model = scan_directory(["tests/fixtures/sideeffect_pkg"], Path.cwd())
    for node in model.modules:
        node.findings = run_static(node, Path(node.file).read_text(encoding="utf-8"))
    classify_all(model)

    assert _classify_module(_analyze_fixture("se06_decorators")) == Classification.RISKY
    assert _classify_module(_analyze_fixture("se04_register")) == Classification.UNSAFE
