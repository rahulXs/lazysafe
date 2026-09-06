"""data models for lazysafe analysis."""

import enum
from dataclasses import dataclass, field


class Origin(enum.Enum):
    """where an import comes from."""

    OWN = "own"
    STDLIB = "stdlib"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class Classification(enum.Enum):
    """side-effect classification for a module."""

    SAFE = "safe"
    RISKY = "risky"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


@dataclass
class SEFinding:
    """a single side-effect finding from a static rule."""

    rule: str
    lineno: int
    evidence: str
    confidence: float


@dataclass
class ImportStmt:
    """a single import statement extracted from source."""

    module: str
    names: list[str]
    lineno: int
    is_try_except: bool = False
    is_lazy: bool = False


@dataclass
class ModuleNode:
    """a module discovered during file walk."""

    module: str
    file: str
    origin: Origin
    imports: list[ImportStmt] = field(default_factory=list)
    findings: list[SEFinding] = field(default_factory=list)
    classification: Classification = Classification.UNKNOWN
    rejected_reasons: list[str] = field(default_factory=list)
    est_reducible_ms: float = 0.0


@dataclass
class ImportModel:
    """full analysis model for a scan."""

    modules: list[ModuleNode] = field(default_factory=list)
    order_constraints: list[dict[str, str]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
