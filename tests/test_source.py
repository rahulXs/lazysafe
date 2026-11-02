from lazysafe.source import build_manifest, find_package_root, manifest_digest


def test_find_package_flat(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text("VALUE=1\n", encoding="utf-8")
    assert find_package_root(tmp_path).name == "pkg"


def test_manifest_stable(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text("VALUE=1\n", encoding="utf-8")
    m1 = build_manifest(tmp_path)
    m2 = build_manifest(tmp_path)
    assert manifest_digest(m1) == manifest_digest(m2)
