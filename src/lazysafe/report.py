"""JSON report writers."""

import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime

from lazysafe._version import __version__

SCHEMA_VERSION = 2

ERROR_INVALID_CONFIG = "invalid_config"
ERROR_COMMAND_UNAVAILABLE = "command_unavailable"
ERROR_INVALID_USAGE = "invalid_usage"
ERROR_INTERNAL = "internal_error"

STABLE_ERROR_CODES = (
    ERROR_INVALID_CONFIG,
    ERROR_COMMAND_UNAVAILABLE,
    ERROR_INVALID_USAGE,
    ERROR_INTERNAL,
)


def _run_id():
    return uuid.uuid4().hex


def _timestamp():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tool():
    return {"name": "lazysafe", "version": __version__}


def _digest_value(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _error_record(code, message, phase="preflight", path=None):
    return {
        "code": code,
        "message": message,
        "phase": phase,
        "path": path,
    }


def error_report(
    code,
    message,
    *,
    phase="preflight",
    path=None,
    kind="error",
    outcome="error",
    run=None,
    coverage=None,
    result=None,
    errors=None,
):
    """Build a schema-2 report for a failed or unavailable invocation."""
    if run is None:
        run = {
            "id": _run_id(),
            "timestamp_utc": _timestamp(),
            "duration_ms": 0.0,
        }
    if coverage is None:
        coverage = {"supported": [], "unavailable": [], "incomplete": []}
    if errors is None:
        errors = [_error_record(code, message, phase, path)]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "tool": _tool(),
        "outcome": outcome,
        "run": run,
        "errors": errors,
        "coverage": coverage,
        "result": result,
    }


# Aliases for callers/tests that use a different spelling.
error_envelope = error_report
make_error_report = error_report
build_error_report = error_report


def write_analysis_report(model, targets, duration_ms):
    by_class = {"safe": 0, "risky": 0, "unsafe": 0, "unknown": 0}
    for m in model.modules:
        by_class[m.classification.value] = by_class.get(m.classification.value, 0) + 1

    selected_targets = list(targets)
    result = {
        "selected_targets": selected_targets,
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
        "dependency_analysis": "not_performed",
    }

    coverage = {
        "supported": ["static_analysis", "classification"],
        "unavailable": ["dependency_analysis", "candidate_eligibility"],
        "incomplete": [],
    }
    if not model.modules:
        coverage["incomplete"].append("no_modules_examined")

    outcome = "completed"
    errors = []
    if any(
        s.get("reason") in {"not-found", "not-a-directory", "unreadable"} for s in model.skipped
    ):
        # Incomplete analysis stays unknown; do not turn it into a clean result.
        pass

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "analysis",
        "tool": _tool(),
        "outcome": outcome,
        "run": {
            "id": _run_id(),
            "timestamp_utc": _timestamp(),
            "duration_ms": round(duration_ms, 1),
            "host_python": (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            ),
            "targets": selected_targets,
        },
        "errors": errors,
        "coverage": coverage,
        "result": result,
    }


def dumps_report(report):
    return json.dumps(report, indent=2, allow_nan=False, ensure_ascii=False)
