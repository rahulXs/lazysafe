from pathlib import Path

import pytest

from lazysafe.trial import parse_trial_config

FIXTURE = Path("tests/fixtures/trial/valid.toml")


def test_valid():
    cfg = parse_trial_config(FIXTURE)
    assert cfg.package == "demo_cli"
    assert len(cfg.scenarios) == 2


def test_duplicate_name(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text(FIXTURE.read_text().replace('name = "render"', 'name = "help"'))
    with pytest.raises(ValueError):
        parse_trial_config(p)
