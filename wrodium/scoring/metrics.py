"""Aggregation: cells -> per-vendor metrics (Stage 5/6).

These are the numbers that reach the leaderboard. Two invariants from the playbook
are enforced structurally here:
  * cost_per_correct is always computed (Rule 3);
  * "no coverage" is `None` (renders '-'), never 0 (Rule 2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .engine import CellScore
from .states import ResultState

# Sentinel: a metric with no data to compute. Publishers render it via the
# primitive's per-metric `dash_semantics`, NOT as the number 0.
DASH: Optional[float] = None


@dataclass
class VendorMetrics:
    vendor: str
    n: int                                  # cohort rows attempted
    accuracy: Optional[float]               # correct / attempts (correct+incorrect)
    coverage: Optional[float]               # attempts / n  (how often it answered at all)
    cost_per_correct: Optional[float]       # billed $ / correct answer
    total_cost_usd: float
    mean_latency_ms: Optional[float]
    state_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor, "n": self.n,
            "accuracy": self.accuracy, "coverage": self.coverage,
            "cost_per_correct": self.cost_per_correct,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "mean_latency_ms": self.mean_latency_ms,
            "state_counts": self.state_counts,
        }


def aggregate_vendor(cells: list[CellScore]) -> VendorMetrics:
    if not cells:
        return VendorMetrics("?", 0, DASH, DASH, DASH, 0.0, DASH)
    vendor = cells[0].vendor
    n = len(cells)
    counts: dict[str, int] = {s.value: 0 for s in ResultState}
    for c in cells:
        counts[c.state.value] += 1

    correct = counts[ResultState.CORRECT.value]
    attempts = correct + counts[ResultState.INCORRECT.value]
    total_cost = sum(c.cost_usd for c in cells)
    latencies = [c.latency_ms for c in cells if c.latency_ms]

    accuracy = (correct / attempts) if attempts else DASH      # no attempts -> '-'
    coverage = attempts / n if n else DASH
    # cost_per_correct: billed cost across ALL calls divided by correct answers.
    cost_per_correct = (total_cost / correct) if correct else DASH
    mean_latency = (sum(latencies) / len(latencies)) if latencies else DASH

    return VendorMetrics(
        vendor=vendor, n=n, accuracy=accuracy, coverage=coverage,
        cost_per_correct=cost_per_correct, total_cost_usd=total_cost,
        mean_latency_ms=mean_latency, state_counts=counts,
    )


def fidelity(cells: list[CellScore]) -> float:
    """Fraction of cells that are CORRECT over all cells. The Stage-3 dry-run check
    asserts fidelity == 1.0 against a mocked perfect vendor (catches scorer bugs)."""
    if not cells:
        return 0.0
    return sum(1 for c in cells if c.state is ResultState.CORRECT) / len(cells)


def overfit_gap(public_cells: list[CellScore], holdout_cells: list[CellScore]) -> Optional[float]:
    """public accuracy minus holdout accuracy, per vendor (Stage 6).

    A large positive gap means a vendor performs better on the published split than
    on the secret one — evidence of dataset leakage / tuning to the public rows.
    Returns None if either split has no scoreable attempts.
    """
    pub = aggregate_vendor(public_cells).accuracy
    hold = aggregate_vendor(holdout_cells).accuracy
    if pub is None or hold is None:
        return None
    return pub - hold
