"""plan data structure and planner logic."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImportRewrite:
    module: str
    lineno: int
    old_line: str
    new_line: str


@dataclass
class SkippedImport:
    module: str
    file: Path
    reason: str


@dataclass
class FileChange:
    path: Path
    rewrites: list[ImportRewrite]


@dataclass
class Plan:
    changes: list[FileChange]
    skipped: list[SkippedImport]


def plan_keyword(model, *, safe_only=True):
    changes = []
    skipped = []

    for node in model.modules:
        if not node.file:
            continue

        file_path = Path(node.file)
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        file_changes = _plan_file(model, file_path, source, tree, safe_only)
        changes.extend(file_changes.changes)
        skipped.extend(file_changes.skipped)

    return Plan(changes=changes, skipped=skipped)


def _plan_file(model, file_path, source, tree, safe_only):
    rewrites = []
    skipped = []

    for stmt in ast.iter_child_nodes(tree):
        if not isinstance(stmt, ast.Import):
            continue

        for alias in stmt.names:
            module = alias.name
            classification = _get_classification(model, module)

            if classification == "safe":
                old_line = _get_line(source, stmt.lineno)
                new_line = _make_lazy_line(old_line, module)
                if new_line != old_line:
                    rewrites.append(ImportRewrite(
                        module=module,
                        lineno=stmt.lineno,
                        old_line=old_line,
                        new_line=new_line,
                    ))
            elif safe_only:
                skipped.append(SkippedImport(
                    module=module,
                    file=file_path,
                    reason=f"classified as {classification}",
                ))

    changes = [FileChange(path=file_path, rewrites=rewrites)] if rewrites else []
    return Plan(changes=changes, skipped=skipped)


def _get_classification(model, module):
    for node in model.modules:
        if node.module == module:
            return node.classification.value
    return "unknown"


def _get_line(source, lineno):
    lines = source.splitlines()
    if 0 < lineno <= len(lines):
        return lines[lineno - 1]
    return ""


def _make_lazy_line(line, module):
    stripped = line.lstrip()

    if not stripped.startswith("import "):
        return line

    if stripped[len("import "):].strip() != module:
        return line

    indent = line[: len(line) - len(stripped)]
    return f"{indent}lazy import {module}"
