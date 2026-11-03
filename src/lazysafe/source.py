"""selected source identity and manifest hashing."""

import hashlib
from pathlib import Path


def _is_regular_file(path):
    return path.is_file() and not path.is_symlink()


def find_package_root(tree_root):
    """Return the selected top-level package directory or None."""
    root = Path(tree_root)
    candidates = []
    for base in (root, root / "src"):
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if (
                child.is_dir()
                and not child.is_symlink()
                and (child / "__init__.py").is_file()
                and child.name.isidentifier()
                and not child.name.startswith("_")
            ):
                candidates.append(child)
    # Distinct, non-nested: require exactly one.
    if len(candidates) != 1:
        return None
    return candidates[0]


def selected_package_dir(tree_root):
    package_dir = find_package_root(tree_root)
    if package_dir is None:
        return None
    return package_dir


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(tree_root, package_dir=None, inputs=None, script_entries=None):  # noqa: C901
    if package_dir is None:
        package_dir = selected_package_dir(tree_root)
    if package_dir is None:
        raise ValueError("no selected package")
    tree_root = Path(tree_root).resolve()
    package_dir = Path(package_dir).resolve()
    if not package_dir.is_relative_to(tree_root):
        raise ValueError("package escapes tree")
    # reject symlinks in selected package
    for path in package_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in selected package")
        if "__pycache__" in path.parts:
            raise ValueError("pycache in selected package")
        if path.suffix == ".pyc":
            raise ValueError("pyc in selected package")
    entries = []
    for path in sorted(package_dir.rglob("*")):
        if path.is_dir():
            continue
        if not _is_regular_file(path):
            raise ValueError("non-regular file in selected package")
        rel = path.relative_to(tree_root).as_posix()
        entries.append({"path": rel, "sha256": _hash_file(path)})
    # inputs
    for item in inputs or []:
        p = (tree_root / item).resolve()
        if not p.is_relative_to(tree_root) or not _is_regular_file(p):
            raise ValueError("invalid input")
        if p.is_symlink():
            raise ValueError("symlink input")
        entries.append({"path": p.relative_to(tree_root).as_posix(), "sha256": _hash_file(p)})
    # script entries
    for item in script_entries or []:
        p = (tree_root / item).resolve()
        if not p.is_relative_to(tree_root) or not _is_regular_file(p):
            raise ValueError("invalid script entry")
        if p.is_symlink():
            raise ValueError("symlink script")
        entries.append({"path": p.relative_to(tree_root).as_posix(), "sha256": _hash_file(p)})
    # dedupe by path, keep sorted
    by_path = {}
    for e in entries:
        by_path[e["path"]] = e["sha256"]
    manifest = {
        "package": package_dir.name,
        "package_dir": package_dir.relative_to(tree_root).as_posix(),
        "files": [{"path": k, "sha256": by_path[k]} for k in sorted(by_path)],
    }
    return manifest


def manifest_digest(manifest):
    import json

    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def compare_inputs(baseline_root, candidate_root, inputs):
    """Return True only when every declared input has identical bytes."""
    from pathlib import Path

    for item in inputs:
        left = Path(baseline_root) / item
        right = Path(candidate_root) / item
        if not left.is_file() or not right.is_file():
            return False
        if left.read_bytes() != right.read_bytes():
            return False
    return True


def manifests_equal(left, right):
    return left == right


def no_source_change(left_manifest, right_manifest):
    return left_manifest == right_manifest
