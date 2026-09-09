"""data models for lazysafe analysis."""

import enum
from dataclasses import dataclass, field


class Origin(enum.Enum):
    OWN = "own"
    STDLIB = "stdlib"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class Classification(enum.Enum):
    SAFE = "safe"
    RISKY = "risky"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


@dataclass
class SEFinding:
    rule: str
    lineno: int
    evidence: str
    confidence: float


@dataclass
class ImportStmt:
    module: str
    names: list[str]
    lineno: int
    is_try_except: bool = False


@dataclass
class ModuleNode:
    module: str
    file: str
    origin: Origin
    imports: list[ImportStmt] = field(default_factory=list)
    findings: list[SEFinding] = field(default_factory=list)
    classification: Classification = Classification.UNKNOWN


@dataclass
class ImportModel:
    modules: list[ModuleNode] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
