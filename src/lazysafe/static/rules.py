"""SE01-SE08 side-effect detection rules."""

import ast

from lazysafe.model import ModuleNode, SEFinding

_SYS_TARGETS = frozenset({"path", "meta_path", "modules"})
_LOGGING_ATTRS = frozenset({"basicConfig", "config"})
_PATH_READ_ATTRS = frozenset({"read_text", "read_bytes"})


def _is_pure_builtin_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id in _PURE_BUILTINS


def _is_importlib_import(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
        and node.func.attr == "import_module"
    )


def _make_finding(
    rule: str, lineno: int, evidence: str, confidence: float
) -> SEFinding:
    return SEFinding(
        rule=rule,
        lineno=lineno,
        evidence=evidence,
        confidence=confidence,
    )


def _check_se01(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        is_call = isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        if is_call and not _is_pure_builtin_call(node.value):
            findings.append(
                _make_finding("SE01", node.lineno, ast.dump(node.value.func), 0.6)
            )

    return findings


def _check_se02(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                is_foreign = (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                )
                if is_foreign:
                    evidence = f"{target.value.id}.{target.attr}"
                    findings.append(_make_finding("SE02", node.lineno, evidence, 0.9))
        elif isinstance(node, ast.AugAssign):
            target = node.target
            is_foreign = (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
            )
            if is_foreign:
                evidence = f"{target.value.id}.{target.attr}"
                findings.append(_make_finding("SE02", node.lineno, evidence, 0.9))

    return findings


def _check_se03(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.Assign, ast.AugAssign)):
            continue

        targets = node.targets if isinstance(node, ast.Assign) else [node.target]

        for target in targets:
            is_subscript = isinstance(target, ast.Subscript)
            if not is_subscript:
                continue
            is_attr = isinstance(target.value, ast.Attribute)
            if not is_attr:
                continue
            is_name = isinstance(target.value.value, ast.Name)
            if not is_name:
                continue

            obj_id = target.value.value.id
            attr = target.value.attr

            if obj_id == "sys" and attr in _SYS_TARGETS:
                evidence = f"sys.{attr}[...]"
                findings.append(_make_finding("SE03", node.lineno, evidence, 0.95))
            elif obj_id == "os" and attr == "environ":
                findings.append(
                    _make_finding("SE03", node.lineno, "os.environ[...]", 0.95)
                )

    return findings


def _check_se04(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        is_call = isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        if not is_call:
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute):
            continue
        obj = call.func.value
        attr = call.func.attr
        if not isinstance(obj, ast.Name):
            continue

        if obj.id == "atexit" and attr == "register":
            findings.append(
                _make_finding("SE04", node.lineno, "atexit.register(...)", 0.9)
            )
        elif obj.id == "signal" and attr == "signal":
            findings.append(
                _make_finding("SE04", node.lineno, "signal.signal(...)", 0.9)
            )
        elif obj.id == "logging" and attr in _LOGGING_ATTRS:
            findings.append(
                _make_finding("SE04", node.lineno, f"logging.{attr}(...)", 0.85)
            )

    return findings


def _check_se05(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "open":
                findings.append(_make_finding("SE05", node.lineno, "open(...)", 0.8))
            elif (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "Path"
                and call.func.attr in _PATH_READ_ATTRS
            ):
                evidence = f"Path(...).{call.func.attr}()"
                findings.append(_make_finding("SE05", node.lineno, evidence, 0.8))
        elif isinstance(node, ast.With):
            for item in node.items:
                is_open = (
                    isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Name)
                    and item.context_expr.func.id == "open"
                )
                if is_open:
                    findings.append(
                        _make_finding("SE05", node.lineno, "open(...)", 0.8)
                    )

    return findings


def _check_se06(tree: ast.Module) -> list[SEFinding]:
    findings = []
    count = 0

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for dec in node.decorator_list:
            is_attr = isinstance(dec, ast.Attribute)
            is_call_attr = (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
            )
            if is_attr or is_call_attr:
                count += 1

    if count >= 2:
        findings.append(
            _make_finding("SE06", 1, f"{count} registration decorators", 0.5)
        )

    return findings


def _check_se07(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        has_call = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)) or (
            isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
        )
        if has_call and _is_importlib_import(node.value):
            findings.append(
                _make_finding(
                    "SE07", node.lineno, "importlib.import_module(...)", 0.9
                )
            )

    return findings


def _is_import_error_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    if isinstance(handler.type, ast.Name):
        return handler.type.id in ("ImportError", "ModuleNotFoundError")
    if isinstance(handler.type, ast.Tuple):
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name) and elt.id in ("ImportError", "ModuleNotFoundError"):
                return True
    return False


def _check_se08(tree: ast.Module) -> list[SEFinding]:
    findings = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _is_import_error_handler(handler):
                continue

            has_patch = any(
                isinstance(stmt, (ast.Assign, ast.Expr))
                for stmt in ast.iter_child_nodes(handler)
            )
            if has_patch:
                findings.append(
                    _make_finding(
                        "SE08",
                        node.lineno,
                        "try/except ImportError with fallback patch",
                        0.7,
                    )
                )

    return findings


def run_static(node: ModuleNode, source: str) -> list[SEFinding]:
    """run all SE rules on a module's source."""
    try:
        tree = ast.parse(source, filename=node.file)
    except SyntaxError:
        return []

    findings = []
    findings.extend(_check_se01(tree))
    findings.extend(_check_se02(tree))
    findings.extend(_check_se03(tree))
    findings.extend(_check_se04(tree))
    findings.extend(_check_se05(tree))
    findings.extend(_check_se06(tree))
    findings.extend(_check_se07(tree))
    findings.extend(_check_se08(tree))

    return findings


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
