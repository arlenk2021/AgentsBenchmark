"""Shared primitives for the wrodium-bench framework.

`Report` is the spine of every gate in the playbook: each stage runs a set of
checks, accumulates `Issue`s, and refuses to advance while any ERROR remains.
This is what turns the prose checklists in the playbook into mechanical gates.
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class Severity(str, Enum):
    ERROR = "error"      # blocks the stage gate
    WARN = "warn"        # surfaced, does not block
    INFO = "info"


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str            # stable, greppable identifier e.g. "metric.missing_cost_per_correct"
    message: str
    where: str = ""      # file path / row id / vendor key for locating it

    def render(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.severity.value.upper():5} {self.code}{loc}: {self.message}"


@dataclass
class Report:
    """Accumulates issues for one stage gate."""
    stage: str
    issues: list[Issue] = field(default_factory=list)

    def error(self, code: str, message: str, where: str = "") -> None:
        self.issues.append(Issue(Severity.ERROR, code, message, where))

    def warn(self, code: str, message: str, where: str = "") -> None:
        self.issues.append(Issue(Severity.WARN, code, message, where))

    def info(self, code: str, message: str, where: str = "") -> None:
        self.issues.append(Issue(Severity.INFO, code, message, where))

    def extend(self, other: "Report") -> None:
        self.issues.extend(other.issues)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARN]

    @property
    def passed(self) -> bool:
        """A gate passes only when no ERROR-severity issues remain."""
        return not self.errors

    def render(self) -> str:
        head = f"=== {self.stage} :: {'PASS' if self.passed else 'FAIL'} "
        head += f"({len(self.errors)} errors, {len(self.warnings)} warnings) ==="
        body = "\n".join(i.render() for i in self.issues) or "  (no issues)"
        return f"{head}\n{body}"


def stable_hash(obj: Any) -> str:
    """Deterministic content hash — used for snapshot immutability and drift checks."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    Path(path).write_text(
        "\n".join(json.dumps(r, sort_keys=True, default=str) for r in rows) + "\n",
        encoding="utf-8",
    )
