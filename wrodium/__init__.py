"""wrodium-bench — the system behind the playbook.

Each stage gate in the operator's playbook is a function here that returns a
`Report`; nothing advances while a gate has ERROR-severity issues. The CLI
(`python -m wrodium ...`) drives the stages end to end.
"""
from .util import Report, Issue, Severity
from . import schema, adapters, scoring, snapshot, publish

__version__ = "0.1.0"

__all__ = ["Report", "Issue", "Severity", "schema", "adapters", "scoring", "snapshot", "publish"]
