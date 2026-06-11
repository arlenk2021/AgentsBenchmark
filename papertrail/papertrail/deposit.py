"""depositback — security-deposit recovery.

Built as papertrail's top-of-funnel product, not a separate company. The funnel logic
(from the market analysis): people search "how do I get my deposit back" calmly and in
volume, while "I'm being evicted" is low-volume, high-distress, and trust-gated. Same
engine, same statute (§ 1950.5), same user — so deposit recovery is the calm front door
that earns the right to sell the eviction kit.

This module computes the dollars at stake and the legality of the deposit itself, then
hands off to letters.deposit_demand for the sendable artifact.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from .citations import cite
from .deadlines import DeadlineEngine, Deadline


@dataclass(frozen=True)
class DepositCapCheck:
    lawful_max: float
    charged: float
    over_cap: bool
    rule: str

    def render(self) -> str:
        verdict = "EXCEEDS the legal cap" if self.over_cap else "within the legal cap"
        return f"Deposit ${self.charged:,.2f} is {verdict} (max ${self.lawful_max:,.2f}). {self.rule}"


@dataclass(frozen=True)
class DepositExposure:
    deposit: float
    base_recoverable: float        # the deposit itself, if withholding isn't perfected
    statutory_damages_max: float   # up to 2x deposit for bad faith (§1950.5(l))
    total_max: float               # base + statutory, the ceiling a tenant could argue
    small_claims_ok: bool          # within the $12,500 individual cap?
    rationale: str


def check_deposit_cap(*, monthly_rent: float, deposit_charged: float,
                      small_landlord: bool = False, service_member: bool = False) -> DepositCapCheck:
    """AB 12 (Civ. Code § 1950.5(c)): since July 1, 2024 a deposit may not exceed one
    month's rent — except a qualifying small landlord may charge two months', and never
    more than one month for a service member."""
    if service_member:
        cap_months, rule = 1, ("Service members are capped at one month's rent regardless of "
                               "the small-landlord exception (AB 12).")
    elif small_landlord:
        cap_months, rule = 2, ("Qualifying small landlord (natural person/LLC, <=2 properties, "
                               "<=4 units): up to two months' rent (AB 12).")
    else:
        cap_months, rule = 1, "Standard cap of one month's rent since July 1, 2024 (AB 12)."
    lawful_max = cap_months * monthly_rent
    return DepositCapCheck(lawful_max, deposit_charged, deposit_charged > lawful_max + 1e-9, rule)


def estimate_exposure(*, deposit: float, withholding_perfected: bool, bad_faith: bool) -> DepositExposure:
    """What a tenant could plausibly recover.

    - If the landlord missed the 21-day accounting, the right to withhold isn't perfected
      (§1950.5(f)) and the full deposit is recoverable.
    - Bad-faith retention adds up to 2x the deposit in statutory damages (§1950.5(l)).
    We report the ceiling, clearly labeled as a maximum a court 'may' award, not a promise."""
    base = 0.0 if withholding_perfected else deposit
    stat = (2.0 * deposit) if bad_faith else 0.0
    total = base + stat
    parts = []
    if not withholding_perfected:
        parts.append("landlord missed the 21-day accounting, so the full deposit is recoverable "
                     "(§1950.5(f))")
    if bad_faith:
        parts.append("bad-faith retention may add up to twice the deposit in statutory damages "
                     "(§1950.5(l)) — a maximum a court 'may' award, not a guarantee")
    if not parts:
        parts.append("withholding appears perfected and no bad faith indicated; recoverable amount "
                     "depends on whether the itemized deductions are valid")
    return DepositExposure(
        deposit=deposit, base_recoverable=base, statutory_damages_max=stat, total_max=total,
        small_claims_ok=total <= 12_500,
        rationale="; ".join(parts) + ".",
    )


@dataclass(frozen=True)
class DepositCase:
    cap_check: DepositCapCheck
    deadline: Deadline
    overdue: bool
    exposure: DepositExposure

    def render(self) -> str:
        lines = [
            "=== Deposit recovery assessment ===",
            self.cap_check.render(),
            "",
            self.deadline.render(),
            f"  Status: {'OVERDUE — accounting deadline has passed' if self.overdue else 'not yet due'}",
            "",
            f"Deposit: ${self.exposure.deposit:,.2f}",
            f"Recoverable (deposit): ${self.exposure.base_recoverable:,.2f}",
            f"Max statutory damages (bad faith, up to 2x): ${self.exposure.statutory_damages_max:,.2f}",
            f"Ceiling total: ${self.exposure.total_max:,.2f} "
            f"({'fits' if self.exposure.small_claims_ok else 'EXCEEDS'} small-claims $12,500 cap)",
            f"  {self.exposure.rationale}",
        ]
        return "\n".join(lines)


def assess_deposit(*, monthly_rent: float, deposit: float, vacated: _dt.date,
                   today: _dt.date | None = None, bad_faith: bool = False,
                   small_landlord: bool = False, service_member: bool = False,
                   engine: DeadlineEngine | None = None) -> DepositCase:
    """End-to-end deposit assessment: cap legality + return deadline + dollar exposure."""
    today = today or _dt.date.today()
    engine = engine or DeadlineEngine()
    cap = check_deposit_cap(monthly_rent=monthly_rent, deposit_charged=deposit,
                            small_landlord=small_landlord, service_member=service_member)
    deadline = engine.deposit_return(vacated)
    overdue = deadline.last_day is not None and today > deadline.last_day
    # If the deadline has passed with no compliant accounting, withholding isn't perfected.
    exposure = estimate_exposure(deposit=deposit, withholding_perfected=not overdue,
                                 bad_faith=bad_faith and overdue)
    return DepositCase(cap, deadline, overdue, exposure)
