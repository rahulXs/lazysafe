"""tests for CLI commands."""

import os
import sys

import pytest

from lazysafe.cli import main

PY = sys.executable


def _write_single_rewrite_fixture(root):
    """Flat fixture whose plan holds exactly one rewrite."""
    # write_bytes, not write_text: that would give \r\n on Windows and break
    # the exact-byte assertions below.
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


class TestMeasureContainment:
    def test_budget_flag_rejected(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "measure",
                    "--runs",
                    "1",
                    "--warmup",
                    "0",
                    "--budget",
                    "100",
                    "--",
                    PY,
                    "-c",
                    "import json",
                ]
            )
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "budget gating is unavailable" in captured.err

    def test_failed_command_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["measure", "--runs", "1", "--warmup", "0", "--", PY, "-c", "raise SystemExit(1)"])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "sample(s) failed" in captured.err

    def test_invalid_counts_rejected_before_launch(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["measure", "--runs", "0", "--warmup", "0", "--", PY, "-c", "pass"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "runs must be >= 1" in captured.err

    def test_successful_run_labels_import_profile(self, capsys):
        main(["measure", "--runs", "1", "--warmup", "0", "--", PY, "-c", "import json"])
        captured = capsys.readouterr()
        assert "import-profile data" in captured.out
        assert "not command duration" in captured.out


class TestAnalyzeIncomplete:
    def test_missing_target_fails(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "does-not-exist"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "does-not-exist" in captured.err
        assert "no such file" in captured.err
        assert "look safe" not in captured.out

    def test_file_target_fails(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "one.py").write_bytes(b"VALUE = 1\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "one.py"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "not a directory" in captured.err
        assert "look safe" not in captured.out

    def test_empty_directory_makes_no_claim(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "."])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "no modules examined" in captured.err
        assert "look safe" not in captured.out
        assert "no side effects detected" not in captured.out

    def test_broken_only_directory_makes_no_claim(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "broken.py").write_bytes(b"def broken(:\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["analyze", "."])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "skipped 1 file(s)" in captured.out
        assert "broken.py" in captured.out
        assert "look safe" not in captured.out

    def test_good_and_broken_directory_warns_but_passes(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "good.py").write_bytes(b"VALUE = 1\n")
        (tmp_path / "broken.py").write_bytes(b"def broken(:\n")
        monkeypatch.chdir(tmp_path)
        main(["analyze", "."])
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
            main(["analyze", "."])
        finally:
            target.chmod(0o644)
        captured = capsys.readouterr()
        assert "skipped 1 file(s)" in captured.out
        assert "noread.py" in captured.out
        assert "look safe" not in captured.out

    def test_clean_scan_qualifies_safe(self, capsys):
        main(["analyze", "tests/fixtures/clean_pkg"])
        captured = capsys.readouterr()
        assert "heuristic, not proof" in captured.out
        assert "look safe" not in captured.out


class TestLiteralArgv:
    """Everything after `--` is one executable and its arguments (LS-03)."""

    def test_executable_path_with_spaces(self, tmp_path, capsys):
        # a wrapper rather than a copied interpreter, which loses its stdlib
        spaced = tmp_path / "dir with spaces"
        spaced.mkdir()
        if os.name == "nt":
            exe = spaced / "py runner.bat"
            exe.write_bytes(f'@echo off\r\n"{PY}" %*\r\n'.encode())
        else:
            exe = spaced / "py runner.sh"
            exe.write_bytes(f'#!/bin/sh\nexec "{PY}" "$@"\n'.encode())
            exe.chmod(0o755)

        main(["measure", "--runs", "1", "--warmup", "0", "--", str(exe), "-c", "import json"])

        assert "import-profile data" in capsys.readouterr().out

    def test_unicode_arguments_survive(self, capsys):
        # the child prints unicode_escape so its own output is ASCII anywhere: a
        # piped stdout on windows uses the local code page, and what this test
        # checks is the argument surviving the argv boundary
        main(
            [
                "measure",
                "--runs",
                "1",
                "--warmup",
                "0",
                "--",
                PY,
                "-c",
                "import sys; print(sys.argv[1].encode('unicode_escape').decode())",
                "héllo → ✓",
            ]
        )
        assert "import-profile data" in capsys.readouterr().out

    def test_python_dash_m_runs_a_module(self, capsys):
        main(["measure", "--runs", "1", "--warmup", "0", "--", PY, "-m", "json.tool", "--help"])
        assert "import-profile data" in capsys.readouterr().out

    def test_exit_code_propagates(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["measure", "--runs", "1", "--warmup", "0", "--", PY, "-c", "raise SystemExit(4)"])
        assert exc_info.value.code == 1
        assert "sample(s) failed" in capsys.readouterr().err

    @pytest.mark.parametrize("flag", ["-c", "-m"])
    def test_leading_flag_without_executable_is_rejected(self, flag, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["measure", flag, "import json"])
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "needs the executable before" in err
        assert f"measure -- python {flag}" in err

    def test_shell_metacharacters_are_literal(self, capsys):
        # shell=False: these reach the program as text, unexpanded and unsplit
        main(
            [
                "measure",
                "--runs",
                "1",
                "--warmup",
                "0",
                "--",
                PY,
                "-c",
                "import sys; print(sys.argv[1])",
                "a b; rm -rf / | $HOME `id` * ?",
            ]
        )
        assert "import-profile data" in capsys.readouterr().out

    def test_no_command_gives_an_example(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["measure"])
        assert exc_info.value.code == 2
        assert "measure -- python -c" in capsys.readouterr().err

    def test_bare_token_is_not_treated_as_a_module(self, capsys):
        # `measure json` used to run `python -c "import json"`
        with pytest.raises(SystemExit) as exc_info:
            main(["measure", "--runs", "1", "--warmup", "0", "--", "json"])
        assert exc_info.value.code == 1
        assert "spawn_error" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("command", "flag"),
        [
            (["measure"], "--python"),
            (["verify"], "--python"),
            (["verify"], "--lazy-python"),
        ],
    )
    def test_removed_interpreter_flags_give_a_migration_hint(self, command, flag, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([*command, flag, PY, "--", PY, "-c", "pass"])
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert f"{flag} was removed" in err
        assert "--`" in err

    def test_probe_keeps_its_python_flag(self, capsys):
        main(["probe", "json", "--python", PY])
        assert "json" in capsys.readouterr().out
