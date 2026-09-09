"""JSON report writers."""

import sys
from datetime import UTC, datetime

from lazysafe._version import __version__
from lazysafe.model import ImportModel


def _json_default(obj: object) -> object:
    if hasattr(obj, "value"):
        return obj.value
    raise TypeError(f"not serializable: {type(obj)}")


def write_analysis_report(
    model: ImportModel,
    targets: list[str],
    duration_ms: float,
) -> dict:
    by_class = {"safe": 0, "risky": 0, "unsafe": 0, "unknown": 0}
    for m in model.modules:
        by_class[m.classification.value] = by_class.get(m.classification.value, 0) + 1

    return {
        "schema_version": 1,
        "tool": {"name": "lazysafe", "version": __version__},
        "run": {
            "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_ms": round(duration_ms, 1),
            "host_python": (
                f"{sys.version_info.major}.{sys.version_info.minor}"
                f".{sys.version_info.micro}"
            ),
            "targets": targets,
        },
        "stats": {
            "files_scanned": len(model.modules),
            "files_skipped": len(model.skipped),
            "top_level_imports": sum(len(m.imports) for m in model.modules),
            "by_class": by_class,
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
            }
            for m in model.modules
        ],
        "skipped": model.skipped,
    }
