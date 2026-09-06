"""file walk and import statement extraction."""

import ast
import sys
from pathlib import Path

from lazysafe.model import ImportModel, ImportStmt, ModuleNode, Origin


def _classify_origin(module: str, own_prefixes: set[str]) -> Origin:
    """classify a module as own, stdlib, third-party, or unknown."""
    top = module.split(".")[0]

    if top in sys.stdlib_module_names:
        return Origin.STDLIB

    if top in own_prefixes:
        return Origin.OWN

    if top in _THIRD_PARTY_TOP_LEVELS:
        return Origin.THIRD_PARTY

    return Origin.UNKNOWN


_THIRD_PARTY_TOP_LEVELS: set[str] = set()


def _refresh_third_party() -> None:
    """populate third-party top-level names from sys.path."""
    global _THIRD_PARTY_TOP_LEVELS
    try:
        import importlib.metadata

        _THIRD_PARTY_TOP_LEVELS = {
            dist.name.split(".")[0].lower().replace("-", "_").replace(" ", "_")
            for dist in importlib.metadata.distributions()
        }
    except Exception:
        _THIRD_PARTY_TOP_LEVELS = set()


def _extract_imports(tree: ast.Module) -> list[ImportStmt]:
    """extract top-level import statements from an AST."""
    imports: list[ImportStmt] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportStmt(
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        lineno=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(
                ImportStmt(
                    module=module,
                    names=names,
                    lineno=node.lineno,
                )
            )
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is not None and isinstance(
                    handler.type, ast.Name
                ):
                    if handler.type.id == "ImportError":
                        for stmt in ast.iter_child_nodes(handler):
                            if isinstance(stmt, ast.Import):
                                for alias in stmt.names:
                                    imports.append(
                                        ImportStmt(
                                            module=alias.name,
                                            names=[alias.asname or alias.name],
                                            lineno=stmt.lineno,
                                            is_try_except=True,
                                        )
                                    )
                            elif isinstance(stmt, ast.ImportFrom):
                                mod = stmt.module or ""
                                names = [a.name for a in stmt.names]
                                imports.append(
                                    ImportStmt(
                                        module=mod,
                                        names=names,
                                        lineno=stmt.lineno,
                                        is_try_except=True,
                                    )
                                )

    return imports


def scan_directory(
    targets: list[str], project_root: Path
) -> ImportModel:
    """walk target directories and build an ImportModel."""
    _refresh_third_party()
    model = ImportModel()

    own_prefixes: set[str] = set()
    for target in targets:
        target_path = project_root / target
        if target_path.exists():
            for py_file in target_path.rglob("*.py"):
                rel = py_file.relative_to(project_root)
                module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
                top = module.split(".")[0]
                if top:
                    own_prefixes.add(top)

    for target in targets:
        target_path = project_root / target
        if not target_path.exists():
            model.skipped.append({"path": target, "reason": "not-found"})
            continue

        for py_file in sorted(target_path.rglob("*.py")):
            rel = py_file.relative_to(project_root)
            module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")

            if module.endswith(".__init__"):
                module = module[: -len(".__init__")]

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError) as exc:
                model.skipped.append(
                    {"path": str(rel), "reason": str(exc)}
                )
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

    return model
