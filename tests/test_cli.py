"""tests for CLI commands."""

from pathlib import Path

import pytest

from lazysafe.cli import main


def _write_single_rewrite_fixture(root: Path) -> Path:
    """Flat fixture whose plan holds exactly one rewrite."""
    # write_bytes: write_text would translate newlines to \r\n on Windows,
    # which breaks the exact-byte assertions below.
    (root / "safe_dep.py").write_bytes(b"VALUE = 1\n")
    consumer = root / "consumer.py"
    consumer.write_bytes(b"import safe_dep\n")
    return consumer


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "lazysafe" in captured.out


def test_analyze_command(capsys):
    main(["analyze", "tests/fixtures/clean_pkg"])
    captured = capsys.readouterr()
    assert "scanned" in captured.out
    assert "files" in captured.out


class TestApplyWritesDisabled:
    def test_write_request_refused_leaves_sources_unchanged(self, tmp_path, monkeypatch, capsys):
        consumer = _write_single_rewrite_fixture(tmp_path)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            main(["apply", "."])

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "1 import(s) to rewrite" in captured.out
        assert "lazy import safe_dep" in captured.out
        assert "cannot write" in captured.err
        assert "recoverable write path" in captured.err
        assert consumer.read_bytes() == b"import safe_dep\n"
        assert not (tmp_path / ".lazysafe").exists()

    def test_write_request_refused_with_include_unsafe(self, tmp_path, monkeypatch, capsys):
        consumer = _write_single_rewrite_fixture(tmp_path)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            main(["apply", ".", "--include-unsafe"])

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "cannot write" in captured.err
        assert consumer.read_bytes() == b"import safe_dep\n"
        assert not (tmp_path / ".lazysafe").exists()

    def test_preview_shows_candidate_without_changes(self, tmp_path, monkeypatch, capsys):
        consumer = _write_single_rewrite_fixture(tmp_path)
        monkeypatch.chdir(tmp_path)

        main(["apply", ".", "--dry-run"])

        captured = capsys.readouterr()
        assert "1 import(s) to rewrite" in captured.out
        assert "lazy import safe_dep" in captured.out
        assert "experimental preview" in captured.out
        assert "no files modified" in captured.out
        assert consumer.read_bytes() == b"import safe_dep\n"
        assert not (tmp_path / ".lazysafe").exists()
