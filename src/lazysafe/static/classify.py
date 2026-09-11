"""classification decision tree and SCC propagation."""

from lazysafe.model import Classification, ImportModel, ModuleNode, Origin


def _classify_module(node: ModuleNode) -> Classification:
    rules = {f.rule for f in node.findings}

    if rules & {"SE02", "SE03", "SE04", "SE07"}:
        return Classification.UNSAFE

    if "SE01" in rules:
        return Classification.RISKY

    if rules & {"SE05", "SE06", "SE08"}:
        return Classification.RISKY

    if node.origin in (Origin.THIRD_PARTY, Origin.UNKNOWN) and not node.findings:
        return Classification.UNKNOWN

    return Classification.SAFE


def classify_all(model: ImportModel):
    for node in model.modules:
        node.classification = _classify_module(node)
