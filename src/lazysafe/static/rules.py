"""SE01-SE08 side-effect detection rules."""

import ast

from lazysafe.model import SEFinding, ModuleNode


def _is_pure_builtin_call(node: ast.Call) -> bool:
    """check if a call is to a known-pure builtin."""
    if isinstance(node.func, ast.Name):
        return node.func.id in _PURE_BUILTINS
    return False


_PURE_BUILTINS = frozenset(
    {
        "len",
        "isinstance",
        "type",
        "repr",
        "hash",
        "bool",
        "int",
        "float",
        "str",
        "dict",
        "list",
        "tuple",
        "set",
        "frozenset",
        "range",
        "enumerate",
        "zip",
        "sorted",
    }
)


def _check_se01(tree: ast.Module) -> list[SEFinding]:
    """SE01: module-level call expressions."""
    findings: list[SEFinding] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if not _is_pure_builtin_call(node.value):
                findings.append(
                    SEFinding(
                        rule="SE01",
                        lineno=node.lineno,
                        evidence=ast.dump(node.value.func),
                        confidence=0.6,
                    )
                )

    return findings


def _check_se02(tree: ast.Module) -> list[SEFinding]:
    """SE02: foreign attribute assignment (monkeypatch detection)."""
    findings: list[SEFinding] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name):
                        findings.append(
                            SEFinding(
                                rule="SE02",
                                lineno=node.lineno,
                                evidence=f"{target.value.id}.{target.attr}",
                                confidence=0.9,
                            )
                        )

    return findings


def _check_se03(tree: ast.Module) -> list[SEFinding]:
    """SE03: import-system / interpreter mutation."""
    findings: list[SEFinding] = []

    _SYS_TARGETS = {"path", "meta_path", "modules"}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Attribute):
                        if isinstance(target.value.value, ast.Name):
                            if target.value.value.id == "sys":
                                if target.value.attr in _SYS_TARGETS:
                                    findings.append(
                                        SEFinding(
                                            rule="SE03",
                                            lineno=node.lineno,
                                            evidence=f"sys.{target.value.attr}[...]",
                                            confidence=0.95,
                                        )
                                    )
                            elif target.value.value.id == "os":
                                if target.value.attr == "environ":
                                    findings.append(
                                        SEFinding(
                                            rule="SE03",
                                            lineno=node.lineno,
                                            evidence="os.environ[...]",
                                            confidence=0.95,
                                        )
                                    )

    return findings


def _check_se04(tree: ast.Module) -> list[SEFinding]:
    """SE04: process-global registrations."""
    findings: list[SEFinding] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute):
                obj = call.func.value
                attr = call.func.attr
                if isinstance(obj, ast.Name):
                    if obj.id == "atexit" and attr == "register":
                        findings.append(
                            SEFinding(
                                rule="SE04",
                                lineno=node.lineno,
                                evidence="atexit.register(...)",
                                confidence=0.9,
                            )
                        )
                    elif obj.id == "signal" and attr == "signal":
                        findings.append(
                            SEFinding(
                                rule="SE04",
                                lineno=node.lineno,
                                evidence="signal.signal(...)",
                                confidence=0.9,
                            )
                        )
                    elif obj.id == "logging":
                        if attr in ("basicConfig", "config"):
                            findings.append(
                                SEFinding(
                                    rule="SE04",
                                    lineno=node.lineno,
                                    evidence=f"logging.{attr}(...)",
                                    confidence=0.85,
                                )
                            )

    return findings


def _check_se05(tree: ast.Module) -> list[SEFinding]:
    """SE05: module-level I/O."""
    findings: list[SEFinding] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name):
                if call.func.id == "open":
                    findings.append(
                        SEFinding(
                            rule="SE05",
                            lineno=node.lineno,
                            evidence="open(...)",
                            confidence=0.8,
                        )
                    )
            elif isinstance(call.func, ast.Attribute):
                if isinstance(call.func.value, ast.Name):
                    if call.func.value.id == "Path":
                        if call.func.attr in ("read_text", "read_bytes"):
                            findings.append(
                                SEFinding(
                                    rule="SE05",
                                    lineno=node.lineno,
                                    evidence=f"Path(...).{call.func.attr}()",
                                    confidence=0.8,
                                )
                            )
        elif isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    call = item.context_expr
                    if isinstance(call.func, ast.Name):
                        if call.func.id == "open":
                            findings.append(
                                SEFinding(
                                    rule="SE05",
                                    lineno=node.lineno,
                                    evidence="open(...)",
                                    confidence=0.8,
                                )
                            )

    return findings


def _check_se06(tree: ast.Module) -> list[SEFinding]:
    """SE06: framework registration decorators."""
    findings: list[SEFinding] = []
    count = 0

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Attribute):
                    count += 1
                elif isinstance(dec, ast.Call) and isinstance(
                    dec.func, ast.Attribute
                ):
                    count += 1

    if count >= 2:
        findings.append(
            SEFinding(
                rule="SE06",
                lineno=1,
                evidence=f"{count} registration decorators",
                confidence=0.5,
            )
        )

    return findings


def _check_se07(tree: ast.Module) -> list[SEFinding]:
    """SE07: entry-point / plugin scanning."""
    findings: list[SEFinding] = []

    for node in ast.iter_child_nodes(tree):
        call = None
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value

        if call is not None:
            if isinstance(call.func, ast.Attribute):
                if isinstance(call.func.value, ast.Name):
                    if call.func.value.id == "importlib":
                        if call.func.attr == "import_module":
                            findings.append(
                                SEFinding(
                                    rule="SE07",
                                    lineno=node.lineno,
                                    evidence="importlib.import_module(...)",
                                    confidence=0.9,
                                )
                            )

    return findings


def _check_se08(tree: ast.Module) -> list[SEFinding]:
    """SE08: conditional-but-unconditional-in-practice imports."""
    findings: list[SEFinding] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is not None and isinstance(handler.type, ast.Name):
                    if handler.type.id == "ImportError":
                        has_patch = False
                        for stmt in ast.iter_child_nodes(handler):
                            if isinstance(stmt, ast.Assign):
                                has_patch = True
                            elif isinstance(stmt, ast.Expr):
                                if isinstance(stmt.value, ast.Call):
                                    has_patch = True
                        if has_patch:
                            findings.append(
                                SEFinding(
                                    rule="SE08",
                                    lineno=node.lineno,
                                    evidence="try/except ImportError with fallback patch",
                                    confidence=0.7,
                                )
                            )

    return findings


def run_static(node: ModuleNode, source: str) -> list[SEFinding]:
    """run all SE rules on a module's source."""
    try:
        tree = ast.parse(source, filename=node.file)
    except SyntaxError:
        return []

    findings: list[SEFinding] = []
    findings.extend(_check_se01(tree))
    findings.extend(_check_se02(tree))
    findings.extend(_check_se03(tree))
    findings.extend(_check_se04(tree))
    findings.extend(_check_se05(tree))
    findings.extend(_check_se06(tree))
    findings.extend(_check_se07(tree))
    findings.extend(_check_se08(tree))

    return findings
