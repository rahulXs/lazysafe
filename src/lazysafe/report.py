"""JSON report writers."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lazysafe._version import __version__
from lazysafe.model import ImportModel


def _json_default(obj: object) -> object:
    """handle non-serializable types."""
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not serializable: {type(obj)}")


def write_analysis_report(
    model: ImportModel,
    targets: list[str],
    duration_ms: float,
    output: Path | None = None,
) -> dict:
    """write an AnalysisReport in JSON format."""
    by_class: dict[str, int] = {"safe": 0, "risky": 0, "unsafe": 0, "unknown": 0}
    for m in model.modules:
        by_class[m.classification.value] = by_class.get(m.classification.value, 0) + 1

    report = {
        "schema_version": 1,
        "tool": {"name": "lazysafe", "version": __version__},
        "run": {
            "timestamp_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "duration_ms": round(duration_ms, 1),
            "host_python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "targets": targets,
            "entries": [],
        },
        "stats": {
            "files_scanned": len(model.modules),
            "files_skipped": len(model.skipped),
            "top_level_imports": sum(len(m.imports) for m in model.modules),
            "candidates": len(model.modules),
            "by_class": by_class,
            "est_reducible_ms_p50": round(
                _median([m.est_reducible_ms for m in model.modules]), 1
            ),
        },
        "modules": [
            {
                "module": m.module,
                "origin": m.origin.value,
                "file": m.file,
                "class": m.classification.value,
                "reasons": [
                    {
                        "rule": f.rule,
                        "lineno": f.lineno,
                        "evidence": f.evidence,
                        "confidence": f.confidence,
                    }
                    for f in m.findings
                ],
                "imports_top_level": [i.module for i in m.imports],
                "subtree_deferred_ms": round(m.est_reducible_ms, 1),
                "probe_ref": None,
            }
            for m in model.modules
        ],
        "skipped": model.skipped,
        "order_constraints": model.order_constraints,
    }

    if output:
        output.write_text(
            json.dumps(report, indent=2, default=_json_default),
            encoding="utf-8",
        )

    return report


def _median(values: list[float]) -> float:
    """compute median of a list."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 0:
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    return sorted_vals[n // 2]
