"""tests for apply planning."""

from pathlib import Path

from lazysafe.apply.plan import _make_lazy_line, plan_keyword
from lazysafe.discovery import scan_directory
from lazysafe.static import run_static
from lazysafe.static.classify import classify_all


def _plan_for(root):
    """Classify a directory and plan rewrites with module names relative to it."""
    model = scan_directory(["."], root)
    for node in model.modules:
        if node.file:
            node.findings = run_static(node, Path(node.file).read_text(encoding="utf-8"))
    classify_all(model)
    return plan_keyword(model, safe_only=True)


def _write_apply_fixture(root):
    # bare module names only resolve when the scan root is the project root
    (root / "safe_dep.py").write_bytes(b"VALUE = 1\n")
    (root / "unsafe_dep.py").write_bytes(b'import sys\n\nsys.path.append("/opt")\n')
    (root / "consumer.py").write_bytes(b"import safe_dep\nimport unsafe_dep\n")


def test_make_lazy_line_preserves_indent_and_leaves_other_forms_alone():
    # a naive rewrite drops the indentation; `from` and already-lazy lines must
    # come back untouched
    assert _make_lazy_line("import json", "json") == "lazy import json"
    assert _make_lazy_line("    import json", "json") == "    lazy import json"
    assert _make_lazy_line("from json import dumps", "json") == "from json import dumps"
    assert _make_lazy_line("lazy import json", "json") == "lazy import json"


def test_plan_rewrites_safe_imports_and_skips_others(tmp_path, monkeypatch):
    _write_apply_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)

    plan = _plan_for(tmp_path)

    assert {r.module for c in plan.changes for r in c.rewrites} == {"safe_dep"}
    assert "unsafe_dep" in {s.module for s in plan.skipped}
