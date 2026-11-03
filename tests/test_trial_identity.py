from lazysafe.source import build_manifest, compare_inputs, no_source_change


def test_inputs_match(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.txt").write_bytes(b"hi")
    (b / "x.txt").write_bytes(b"hi")
    assert compare_inputs(a, b, ["x.txt"]) is True


def test_no_source_change(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    pkg = a / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    pkg2 = b / "pkg"
    pkg2.mkdir()
    (pkg2 / "__init__.py").write_text("")
    ma = build_manifest(a)
    mb = build_manifest(b)
    assert no_source_change(ma, mb) is True
