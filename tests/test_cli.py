"""tests for CLI commands."""

from lazysafe.cli import main


def test_version_command(capsys):
    main(["version"])
    captured = capsys.readouterr()
    assert "lazysafe 0.1.0" in captured.out
    assert "analyze" in captured.out


def test_analyze_command(capsys):
    main(["analyze", "tests/fixtures/clean_pkg"])
    captured = capsys.readouterr()
    assert "scanned" in captured.out
    assert "files" in captured.out
