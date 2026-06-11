"""papertrail — a renter's deadline + evidence + letter kit for California.

The flagship of the four side projects. Built on one verified core (the deadline engine,
gated at 100% by bench/) and one statute registry (citations.py), with depositback folded
in as the calm top-of-funnel module. Designed against two failure modes that have sunk
similar products: legal hallucination (every fact is sourced) and UPL (information + the
user's own words, never representation).
"""
from .calendar_ca import CaliforniaCalendar
from .deadlines import DeadlineEngine, Deadline
from .classify import classify, Classification
from .evidence import EvidenceLog, Entry
from .letters import deposit_demand, deadline_summary, Letter, DISCLAIMER
from .deposit import assess_deposit, check_deposit_cap, estimate_exposure, DepositCase
from .citations import cite, CITATIONS, stale_citations

__version__ = "0.1.0"

__all__ = [
    "CaliforniaCalendar", "DeadlineEngine", "Deadline",
    "classify", "Classification",
    "EvidenceLog", "Entry",
    "deposit_demand", "deadline_summary", "Letter", "DISCLAIMER",
    "assess_deposit", "check_deposit_cap", "estimate_exposure", "DepositCase",
    "cite", "CITATIONS", "stale_citations",
]
