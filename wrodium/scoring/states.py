"""Terminal result states for a single scored cell.

A "cell" is one (vendor, golden row) pair. Exactly one state is assigned. The
distinction between `no_coverage` and the failure states matters for publishing:
`no_coverage` renders as `-` (per each metric's dash_semantics), it is NOT a zero.
"""
from __future__ import annotations

from enum import Enum


class ResultState(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    NO_COVERAGE = "no_coverage"     # vendor returned nothing for this item -> renders as '-'
    BLOCKED = "blocked"             # auth/payment/forbidden (401/402/403)
    TIMEOUT = "timeout"
    FETCH_FAILED = "fetch_failed"

    @property
    def is_attempt(self) -> bool:
        """Did the vendor produce a scoreable answer? Only correct/incorrect count
        toward accuracy denominators; the rest are coverage/availability signals."""
        return self in (ResultState.CORRECT, ResultState.INCORRECT)
