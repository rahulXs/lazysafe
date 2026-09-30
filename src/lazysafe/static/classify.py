"""classify each scanned module from its findings."""

from lazysafe.model import Classification, Origin

_UNSAFE_RULES = {"SE02", "SE03", "SE04", "SE07"}
_RISKY_RULES = {"SE01", "SE05", "SE06", "SE08"}


def _classify_module(node):
    if node.coverage_gaps:
        return Classification.UNKNOWN

    rules = {f.rule for f in node.findings}

    if rules & _UNSAFE_RULES:
        return Classification.UNSAFE

    if rules & _RISKY_RULES:
        return Classification.RISKY

    if node.origin in (Origin.THIRD_PARTY, Origin.UNKNOWN) and not node.findings:
        return Classification.UNKNOWN

    return Classification.SAFE


def classify_all(model):
    for node in model.modules:
        node.classification = _classify_module(node)
