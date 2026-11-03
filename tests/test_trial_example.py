from examples.trial.prepare import main as prepare_main


def test_prepare_refuses_existing(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    with __import__("pytest").raises(SystemExit):
        prepare_main(["--output", str(out)])


def test_prepare_creates_trees(tmp_path):
    out = tmp_path / "demo"
    prepare_main(["--output", str(out)])
    assert (out / "original" / "src" / "demo_cli" / "__init__.py").is_file()
    assert (out / "lazy-candidate" / "src" / "demo_cli" / "main.py").is_file()
