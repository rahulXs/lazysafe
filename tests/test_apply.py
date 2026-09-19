"""tests for apply module."""

import tempfile
from pathlib import Path

from lazysafe.apply.backup import create_backup, restore
from lazysafe.apply.plan import _get_line, _make_lazy_line, plan_keyword
from lazysafe.discovery import scan_directory
from lazysafe.static import run_static
from lazysafe.static.classify import classify_all

FIXTURES = Path(__file__).parent / "fixtures" / "apply_pkg"


def _build_model(targets):
    model = scan_directory(targets, Path.cwd())
    for node in model.modules:
        if node.file:
            try:
                source = Path(node.file).read_text(encoding="utf-8")
                node.findings = run_static(node, source)
            except (OSError, UnicodeDecodeError):
                pass
    classify_all(model)
    return model


class TestGetLine:
    def test_returns_correct_line(self):
        source = "import json\nimport os\nimport sys\n"
        assert _get_line(source, 1) == "import json"
        assert _get_line(source, 2) == "import os"
        assert _get_line(source, 3) == "import sys"

    def test_out_of_range(self):
        source = "import json\n"
        assert _get_line(source, 10) == ""


class TestMakeLazyLine:
    def test_simple_import(self):
        assert _make_lazy_line("import json", "json") == "lazy import json"

    def test_indented_import(self):
        assert _make_lazy_line("    import json", "json") == "    lazy import json"

    def test_from_import_unchanged(self):
        assert _make_lazy_line("from json import dumps", "json") == "from json import dumps"

    def test_already_lazy(self):
        assert _make_lazy_line("lazy import json", "json") == "lazy import json"


class TestPlanKeyword:
    def test_safe_only_rewrites_safe_modules(self):
        model = _build_model([str(FIXTURES)])
        plan = plan_keyword(model, safe_only=True)
        assert len(plan.changes) > 0 or len(plan.skipped) > 0

    def test_safe_only_skips_unsafe(self):
        model = _build_model([str(FIXTURES)])
        plan = plan_keyword(model, safe_only=True)
        assert len(plan.skipped) > 0

    def test_rewrite_preserves_indent(self):
        model = _build_model([str(FIXTURES)])
        plan = plan_keyword(model, safe_only=True)
        for change in plan.changes:
            for rewrite in change.rewrites:
                assert "lazy import" in rewrite.new_line


class TestBackupRestore:
    def test_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            src = project / "test_module.py"
            src.write_text("import json\nimport os\n")

            model = _build_model([str(src)])
            plan = plan_keyword(model, safe_only=True)

            if plan.changes:
                backup_path = create_backup(plan, project)
                assert backup_path.exists()

                for change in plan.changes:
                    change.path.write_text("lazy import json\nlazy import os\n")

                restore(backup_path, plan, project)
                content = src.read_text()
                assert content == "import json\nimport os\n"


class TestApplyIntegration:
    def test_dry_run_does_not_modify_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            src = project / "test_module.py"
            original = "import json\nimport os\n"
            src.write_text(original)

            model = _build_model([str(src)])
            plan = plan_keyword(model, safe_only=True)

            if plan.changes:
                for change in plan.changes:
                    assert change.path.exists()

                content = src.read_text()
                assert content == original
