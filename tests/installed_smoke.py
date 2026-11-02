"""Installed-package smoke checks using only the standard library."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "lazysafe", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def main():
    result = run(["--version"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "lazysafe 0.9.0", result.stdout

    result = run(["--help"])
    assert result.returncode == 0, result.stderr

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "good.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")

        result = run(["analyze", "."], cwd=root)
        assert result.returncode == 3, (result.returncode, result.stdout, result.stderr)
        assert "skipped 1 file(s)" in result.stdout
        assert "broken.py" in result.stdout

        result = run(["analyze", "--json", "."], cwd=root)
        assert result.returncode == 3, (result.returncode, result.stdout, result.stderr)
        report = json.loads(result.stdout)
        assert report["schema_version"] == 2
        assert report["kind"] == "analysis"
        assert report["outcome"] == "completed"

        for command in ("verify", "probe", "apply"):
            result = run([command], cwd=root)
            assert result.returncode == 2, (command, result.returncode, result.stderr)
            assert "command_unavailable" in result.stderr or "unavailable" in result.stderr

        result = run(["analyze", "--json", "does-not-exist"], cwd=root)
        assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
        report = json.loads(result.stdout)
        assert report["kind"] == "error"
        assert report["result"] is None
        assert report["errors"][0]["code"] == "invalid_config"

    print("installed smoke: ok")


if __name__ == "__main__":
    main()
