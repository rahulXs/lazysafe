"""classify each scanned module from its findings."""

from lazysafe.model import Classification

_UNSAFE_RULES = {"SE02", "SE03", "SE04", "SE07"}
_RISKY_RULES = {"SE01", "SE05", "SE06", "SE08"}


def _classify_module(node):
    rules = {f.rule for f in node.findings}

    if rules & _UNSAFE_RULES:
        return Classification.UNSAFE

    if rules & _RISKY_RULES:
        return Classification.RISKY

    # No finding is not proof of safety. Keep the heuristic explicit as a
    # coverage gap so an empty result can never read as eligibility.
    node.coverage_gaps.append("heuristic_coverage_incomplete")
    return Classification.UNKNOWN


def classify_all(model):
    for node in model.modules:
        node.classification = _classify_module(node)
