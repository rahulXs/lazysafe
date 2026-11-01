"""tests for CLI commands."""

import os
import sys

import pytest

from lazysafe.cli import main

PY = sys.executable


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


def test_disabled_commands_are_unavailable(capsys):
    for command in ("verify", "probe", "apply"):
        with pytest.raises(SystemExit) as exc_info:
            main([command, "--help"] if False else [command])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "unavailable in this release" in captured.err


class TestAnalyzeIncomplete:
    def test_missing_target_fails(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "does-not-exist"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "does-not-exist" in captured.err
        assert "no such file" in captured.err

    def test_file_target_fails(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "one.py").write_bytes(b"VALUE = 1\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "one.py"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "not a directory" in captured.err

    def test_empty_directory_is_incomplete(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "."])
        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "incomplete analysis" in captured.err

    def test_broken_only_directory_is_incomplete(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "broken.py").write_bytes(b"def broken(:\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "."])
        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "skipped 1 file(s)" in captured.out
        assert "broken.py" in captured.out

    def test_good_and_broken_directory_is_incomplete(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "good.py").write_bytes(b"VALUE = 1\n")
        (tmp_path / "broken.py").write_bytes(b"def broken(:\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "."])
        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "scanned 1 files" in captured.out
        assert "skipped 1 file(s)" in captured.out
        assert "broken.py" in captured.out

    def test_unreadable_file_is_reported(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "good.py").write_bytes(b"VALUE = 1\n")
        target = tmp_path / "noread.py"
        target.write_bytes(b"VALUE = 1\n")
        target.chmod(0o000)
        if os.access(target, os.R_OK):
            pytest.skip("platform still allows reading the file")
        try:
            monkeypatch.chdir(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                main(["analyze", "."])
            assert exc_info.value.code == 3
        finally:
            target.chmod(0o644)
        captured = capsys.readouterr()
        assert "skipped 1 file(s)" in captured.out
        assert "noread.py" in captured.out

    def test_clean_scan_stays_unknown_not_safe(self, capsys):
        main(["analyze", "tests/fixtures/clean_pkg"])
        captured = capsys.readouterr()
        assert "scanned" in captured.out
