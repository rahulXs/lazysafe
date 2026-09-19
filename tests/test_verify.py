"""tests for verify module."""

import sys

from lazysafe.verify import _normalize, _run_command, verify


class TestNormalize:
    def test_strips_durations(self):
        text = "took 123.45ms"
        assert _normalize(text) == "took Xms"

    def test_strips_seconds(self):
        text = "took 1.23s"
        assert _normalize(text) == "took Xs"

    def test_strips_temp_paths(self):
        text = "file /tmp/abc123"
        assert _normalize(text) == "file TMP_PATH"

    def test_strips_hex_addresses(self):
        text = "object at 0x7f123456"
        assert _normalize(text) == "object at 0xADDR"

    def test_strips_python_version(self):
        text = "running on Python 3.14.7"
        assert _normalize(text) == "running on Python X.Y.Z"

    def test_multiple_normalizations(self):
        text = "took 123.45ms at 0x7f123456"
        result = _normalize(text)
        assert "Xms" in result
        assert "0xADDR" in result


class TestRunCommand:
    def test_runs_successfully(self):
        result = _run_command(["-c", "print('hello')"], sys.executable)
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_bad_command(self):
        result = _run_command(["-c", "import nonexistent_xyz"], sys.executable)
        assert result.exit_code != 0

    def test_timeout(self):
        result = _run_command(["-c", "import time; time.sleep(600)"], sys.executable, timeout=1)
        assert result.exit_code == -1


class TestVerify:
    def test_equivalent_commands(self):
        result = verify(["-c", "print('hello')"], python=sys.executable)
        assert result.equivalent is True
        assert result.eager.exit_code == 0
        assert result.lazy.exit_code == 0

    def test_divergent_exit_codes(self):
        import os
        env_flag = "LAZYSAFE_TEST_DIVERGENT"
        cmd = ["-c", f"import os; os.environ.get('{env_flag}') and os.exit(1)"]

        os.environ[env_flag] = "1"
        try:
            result = verify(cmd, python=sys.executable)
            assert result.equivalent is True
        finally:
            del os.environ[env_flag]
