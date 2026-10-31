"""tests for config loading."""

import pytest

from lazysafe.config import load_config


def test_load_config_missing_file(tmp_path):
    config = load_config(tmp_path)
    assert config.targets == ["src"]


def test_load_config_valid(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("""
targets = ["lib", "src"]
""")
    config = load_config(tmp_path)
    assert config.targets == ["lib", "src"]


def test_load_config_targets_integer(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("targets = 42\n")
    with pytest.raises(ValueError, match="must be a list of strings"):
        load_config(tmp_path)


def test_load_config_targets_string(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text('targets = "src"\n')
    with pytest.raises(ValueError, match="must be a list of strings"):
        load_config(tmp_path)


def test_load_config_targets_non_string_item(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text('targets = ["src", 7]\n')
    with pytest.raises(ValueError, match="must contain only strings"):
        load_config(tmp_path)


def test_load_config_invalid_toml(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("targets = [")
    with pytest.raises(ValueError, match="invalid TOML"):
        load_config(tmp_path)


def test_load_config_unknown_key(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("unknown_key = true\n")
    with pytest.raises(ValueError, match="unknown config keys"):
        load_config(tmp_path)


def test_load_config_unknown_keys_sorted(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("zeta = 1\nalpha = 2\n")
    with pytest.raises(ValueError, match=r"'alpha'.*'zeta'"):
        load_config(tmp_path)


def test_load_config_removed_allowlist(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text('allowlist = ["m"]\n')
    with pytest.raises(ValueError, match="removed config key"):
        load_config(tmp_path)


def test_load_config_inactive_budget_ms(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("budget_ms = 200\n")
    with pytest.raises(ValueError, match="inactive config keys"):
        load_config(tmp_path)


def test_load_config_inactive_measure_runs(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("measure_runs = 3\n")
    with pytest.raises(ValueError, match="measure_runs"):
        load_config(tmp_path)


def test_load_config_inactive_measure_warmup(tmp_path):
    tmp_path.joinpath("lazysafe.toml").write_text("measure_warmup = 1\n")
    with pytest.raises(ValueError, match="measure_warmup"):
        load_config(tmp_path)
