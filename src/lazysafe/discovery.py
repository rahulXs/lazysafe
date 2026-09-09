"""file walk and import statement extraction."""

import ast
import sys
from pathlib import Path

from lazysafe.model import ImportModel, ImportStmt, ModuleNode, Origin


def _classify_origin(module: str, own_prefixes: set[str]) -> Origin:
    top = module.split(".")[0]

    if top in sys.stdlib_module_names:
        return Origin.STDLIB

    if top in own_prefixes:
        return Origin.OWN

    if top in _THIRD_PARTY_TOP_LEVELS:
        return Origin.THIRD_PARTY

    return Origin.UNKNOWN


_THIRD_PARTY_TOP_LEVELS = set()


def _refresh_third_party():
    global _THIRD_PARTY_TOP_LEVELS
    try:
        import importlib.metadata

        _THIRD_PARTY_TOP_LEVELS = {
            dist.name.split(".")[0].lower().replace("-", "_").replace(" ", "_")
            for dist in importlib.metadata.distributions()
        }
    except Exception:
        _THIRD_PARTY_TOP_LEVELS = set()


def _make_import(
    module: str, names: list[str], lineno: int, is_try_except: bool = False
) -> ImportStmt:
    return ImportStmt(
        module=module,
        names=names,
        lineno=lineno,
        is_try_except=is_try_except,
    )


def _extract_imports_from_handler(handler: ast.ExceptHandler) -> list[ImportStmt]:
    imports = []

    for stmt in ast.iter_child_nodes(handler):
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                imports.append(
                    _make_import(
                        alias.name,
                        [alias.asname or alias.name],
                        stmt.lineno,
                        is_try_except=True,
                    )
                )
        elif isinstance(stmt, ast.ImportFrom):
            mod = stmt.module or ""
            names = [a.name for a in stmt.names]
            imports.append(
                _make_import(mod, names, stmt.lineno, is_try_except=True)
            )

    return imports


def _extract_imports(tree: ast.Module) -> list[ImportStmt]:
    imports = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    _make_import(alias.name, [alias.asname or alias.name], node.lineno)
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(_make_import(module, names, node.lineno))
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                is_import_error = (
                    handler.type is not None
                    and isinstance(handler.type, ast.Name)
                    and handler.type.id == "ImportError"
                )
                if is_import_error:
                    imports.extend(_extract_imports_from_handler(handler))

    return imports


def _resolve_target(target: str, project_root: Path) -> Path:
    target_path = Path(target).resolve()
    if not target_path.is_absolute():
        target_path = (project_root / target).resolve()
    return target_path


def _relative_to_any(path: Path, root: Path, fallback: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path.relative_to(fallback)


def _collect_own_prefixes(
    targets: list[str], project_root: Path
) -> set[str]:
    own_prefixes = set()
    for target in targets:
        target_path = _resolve_target(target, project_root)
        if target_path.exists():
            for py_file in target_path.rglob("*.py"):
                rel = _relative_to_any(py_file, project_root, target_path.parent)
                module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
                top = module.split(".")[0]
                if top:
                    own_prefixes.add(top)
    return own_prefixes


def _scan_target(
    target: str,
    project_root: Path,
    own_prefixes: set[str],
    model: ImportModel,
):
    target_path = _resolve_target(target, project_root)
    if not target_path.exists():
        model.skipped.append({"path": target, "reason": "not-found"})
        return

    for py_file in sorted(target_path.rglob("*.py")):
        rel = _relative_to_any(py_file, project_root, target_path.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")

        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError) as exc:
            model.skipped.append({"path": str(rel), "reason": str(exc)})
            continue

        origin = _classify_origin(module, own_prefixes)
        imports = _extract_imports(tree)

        node = ModuleNode(
            module=module,
            file=str(rel),
            origin=origin,
            imports=imports,
        )
        model.modules.append(node)


def scan_directory(
    targets: list[str], project_root: Path
) -> ImportModel:
    _refresh_third_party()
    model = ImportModel()
    own_prefixes = _collect_own_prefixes(targets, project_root)

    for target in targets:
        _scan_target(target, project_root, own_prefixes, model)

    return model
