"""tests for static analysis rules SE01-SE08."""

from pathlib import Path

from lazysafe.discovery import scan_directory
from lazysafe.model import Classification, Origin
from lazysafe.static import run_static
from lazysafe.static.classify import classify_all


FIXTURES = Path(__file__).parent / "fixtures"


def _analyze_fixture(name: str):
    """scan a single fixture file and return the module node."""
    path = FIXTURES / "sideeffect_pkg" / f"{name}.py"
    source = path.read_text()
    model = scan_directory(["tests/fixtures/sideeffect_pkg"], Path.cwd())
    for node in model.modules:
        if node.file.endswith(name + ".py"):
            node.findings = run_static(node, source)
            return node
    return None


def test_se01_detects_module_level_calls():
    node = _analyze_fixture("se01_call")
    rules = {f.rule for f in node.findings}
    assert "SE01" in rules
    assert "SE04" in rules


def test_se02_detects_foreign_assignment():
    node = _analyze_fixture("se02_assign")
    rules = {f.rule for f in node.findings}
    assert "SE02" in rules


def test_se03_detects_sys_mutation():
    node = _analyze_fixture("se03_sys")
    rules = {f.rule for f in node.findings}
    assert "SE03" in rules


def test_se04_detects_registrations():
    node = _analyze_fixture("se04_register")
    rules = {f.rule for f in node.findings}
    assert "SE04" in rules


def test_se05_detects_module_level_io():
    node = _analyze_fixture("se05_io")
    rules = {f.rule for f in node.findings}
    assert "SE05" in rules


def test_se07_detects_import_module():
    node = _analyze_fixture("se07_importlib")
    rules = {f.rule for f in node.findings}
    assert "SE07" in rules


def test_se08_detects_try_except_fallback():
    node = _analyze_fixture("se08_tryexcept")
    rules = {f.rule for f in node.findings}
    assert "SE08" in rules


def test_clean_package_classifies_safe():
    model = scan_directory(["tests/fixtures/clean_pkg"], Path.cwd())
    for node in model.modules:
        source = Path(node.file).read_text()
        node.findings = run_static(node, source)
    classify_all(model)
    for node in model.modules:
        if node.origin == Origin.OWN:
            assert node.classification in (Classification.SAFE, Classification.UNKNOWN)


def test_sideeffect_package_classifies_unsafe():
    model = scan_directory(["tests/fixtures/sideeffect_pkg"], Path.cwd())
    for node in model.modules:
        source = Path(node.file).read_text()
        node.findings = run_static(node, source)
    classify_all(model)
    unsafe = [n for n in model.modules if n.classification == Classification.UNSAFE]
    assert len(unsafe) >= 4
