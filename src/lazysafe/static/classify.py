"""classification decision tree and SCC propagation."""

from lazysafe.model import Classification, ImportModel, ModuleNode, Origin


def _classify_module(node: ModuleNode) -> Classification:
    """classify a module based on its findings."""
    rules = {f.rule for f in node.findings}

    if rules & {"SE02", "SE03", "SE04", "SE07"}:
        return Classification.UNSAFE

    if "SE01" in rules:
        for f in node.findings:
            if f.rule == "SE01" and f.confidence >= 0.6:
                return Classification.RISKY

    if rules & {"SE05", "SE08"}:
        return Classification.RISKY

    se06_count = sum(1 for f in node.findings if f.rule == "SE06")
    if se06_count >= 2:
        return Classification.RISKY

    if node.origin in (Origin.THIRD_PARTY, Origin.UNKNOWN) and not node.findings:
        return Classification.UNKNOWN

    return Classification.SAFE


def classify_all(model: ImportModel) -> None:
    """classify all modules in the model."""
    for node in model.modules:
        node.classification = _classify_module(node)
