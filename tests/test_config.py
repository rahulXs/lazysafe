"""tests for config loading."""

import pytest

from lazysafe.config import load_config


def test_load_config_missing_file(tmp_path):
    config = load_config(tmp_path)
    assert config.targets == ["src"]


def test_load_config_valid(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("""
targets = ["lib", "src"]
budget_ms = 200
""")
    config = load_config(tmp_path)
    assert config.targets == ["lib", "src"]
    assert config.budget_ms == 200


def test_load_config_unknown_key(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("""
unknown_key = true
""")
    with pytest.raises(ValueError, match="unknown config key"):
        load_config(tmp_path)
