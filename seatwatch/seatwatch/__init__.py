"""seatwatch — real-time course-seat alerts.

Deliberately lean (per the analysis: Coursicle owns this category at ~2M students,
bootstrapped, $4.99/semester; the moat is scraping infra, not a new wedge). Included for
portfolio breadth and to keep the diff/notify core clean and testable. The interesting
extension is registrar depth (CalCentral waitlist position, section-swap), modeled as the
SeatSource adapter contract.
"""
from .core import (
    SeatState, Section, SeatSource, Notifier, CollectingNotifier,
    Transition, TransitionKind, diff_snapshots, Watcher, ALERT_ON,
)

__version__ = "0.1.0"
__all__ = [
    "SeatState", "Section", "SeatSource", "Notifier", "CollectingNotifier",
    "Transition", "TransitionKind", "diff_snapshots", "Watcher", "ALERT_ON",
]
