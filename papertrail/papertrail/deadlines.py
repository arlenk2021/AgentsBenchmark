"""The verified deadline engine.

Each function maps a (notice/event date, facts) input to a `Deadline` that carries:
  * the computed last day to act,
  * the counting mode and the statute it comes from,
  * a plain-English explanation and the days excluded.

Design rule (papertrail's Stage-1 kill criterion): this engine must score 100% on the
benchmark in `bench/`. If a case is ambiguous, it returns `confidence="needs_review"`
and refuses to assert a date, because a wrong deadline is the unrecoverable failure.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from .calendar_ca import CaliforniaCalendar
from .citations import cite, Citation


@dataclass(frozen=True)
class Deadline:
    kind: str                       # e.g. "ud_answer", "pay_or_quit", "deposit_return"
    last_day: _dt.date | None
    mode: str                       # "court" | "calendar"
    citation: Citation
    explanation: str
    days_excluded: tuple[str, ...] = ()
    confidence: str = "high"        # "high" | "needs_review"
    notes: tuple[str, ...] = ()

    def render(self) -> str:
        head = (f"{self.kind}: {self.last_day.isoformat() if self.last_day else 'NEEDS REVIEW'} "
                f"({self.mode} days)")
        return f"{head}\n  {self.explanation}\n  Authority: {self.citation.title} — {self.citation.url}"


class DeadlineEngine:
    def __init__(self, calendar: CaliforniaCalendar | None = None) -> None:
        self.cal = calendar or CaliforniaCalendar()

    # ---- 3-day notice to pay rent or quit (CCP § 1161(2)) -------------------

    def pay_or_quit(self, served: _dt.date) -> Deadline:
        """Last court day for the tenant to pay/cure before the landlord may file a UD.
        Counted as 3 court days, excluding weekends and judicial holidays."""
        last = self.cal.add_court_days(served, 3)
        excluded = self._excluded_between(served, last)
        return Deadline(
            kind="pay_or_quit",
            last_day=last, mode="court", citation=cite("ccp_1161"),
            explanation=(f"A 3-day notice served on {served:%a %Y-%m-%d} gives until end of "
                         f"{last:%a %Y-%m-%d} to pay or cure. Saturdays, Sundays, and judicial "
                         f"holidays do not count."),
            days_excluded=excluded,
        )

    # ---- Unlawful-detainer answer (CCP § 1167, post-AB 2347) ---------------

    def ud_answer(self, served: _dt.date, *, service_method: str = "personal") -> Deadline:
        """Last court day to FILE a response to a UD summons: 10 court days after service.

        Personal service starts the clock on service. Substituted service ('nail & mail'
        under CCP §415.20) adds extra days for completion of service; that determination
        is fact-specific, so we flag it for review rather than guess a wrong date."""
        if service_method not in ("personal", "substituted", "posting_mailing", "mail"):
            raise ValueError(f"unknown service_method '{service_method}'")
        if service_method != "personal":
            return Deadline(
                kind="ud_answer", last_day=None, mode="court", citation=cite("ccp_1167"),
                explanation=("Service was not personal. The 10-court-day answer clock may not "
                             "start until service is legally complete (substituted/posting "
                             "service adds time under CCP §415.20/§1011). This is fact-specific — "
                             "confirm the completion-of-service date before relying on a deadline."),
                confidence="needs_review",
                notes=("Do not assert a date for non-personal service without the completion date.",),
            )
        last = self.cal.add_court_days(served, 10)
        return Deadline(
            kind="ud_answer", last_day=last, mode="court", citation=cite("ccp_1167"),
            explanation=(f"A UD summons personally served on {served:%a %Y-%m-%d} requires a "
                         f"response filed by end of {last:%a %Y-%m-%d} — 10 COURT days "
                         f"(AB 2347 doubled this from 5 effective Jan 1, 2025)."),
            days_excluded=self._excluded_between(served, last),
            notes=("Filing late risks a default judgment — the most common way CA tenants lose.",),
        )

    # ---- No-fault termination notice (Civ. Code § 1946.1) ------------------

    def termination_notice(self, served: _dt.date, *, tenancy_start: _dt.date | None = None,
                           occupancy_days: int | None = None) -> Deadline:
        """Earliest valid termination date the landlord could specify: 30 calendar days
        if the tenant occupied < 1 year, else 60 calendar days. This is a duration the
        LANDLORD must give; we compute the soonest lawful end date so a tenant can spot a
        defective (too-short) notice."""
        years_known = tenancy_start is not None or occupancy_days is not None
        if not years_known:
            return Deadline(
                kind="termination_notice", last_day=None, mode="calendar",
                citation=cite("civ_1946_1"),
                explanation="Need the tenancy start date (or occupancy length) to decide "
                            "30- vs 60-day notice.",
                confidence="needs_review",
            )
        if occupancy_days is None:
            occupancy_days = (served - tenancy_start).days
        at_least_one_year = occupancy_days >= 365
        n = 60 if at_least_one_year else 30
        earliest = self.cal.add_calendar_days(served, n)
        return Deadline(
            kind="termination_notice", last_day=earliest, mode="calendar",
            citation=cite("civ_1946_1"),
            explanation=(f"Tenant occupied ~{occupancy_days} days "
                         f"({'>= 1 year' if at_least_one_year else '< 1 year'}), so the landlord "
                         f"must give {n} calendar days. A notice served {served:%Y-%m-%d} cannot "
                         f"set a termination date before {earliest:%Y-%m-%d}; an earlier date is "
                         f"defective."),
            notes=("A too-short notice is void — Civ. Code § 1946.1 rights cannot be waived.",),
        )

    # ---- Security-deposit return clock (Civ. Code § 1950.5(g)) -------------

    def deposit_return(self, vacated: _dt.date) -> Deadline:
        """The landlord's hard deadline to return the deposit + itemized statement: 21
        CALENDAR days after the tenant vacates. Unlike a filing deadline, this duty date
        does NOT roll forward off a weekend — it is a fixed statutory count. After it
        passes with no accounting, the right to withhold is forfeited (§1950.5(f))."""
        due = self.cal.add_calendar_days(vacated, 21)
        return Deadline(
            kind="deposit_return", last_day=due, mode="calendar", citation=cite("civ_1950_5"),
            explanation=(f"Tenant vacated {vacated:%Y-%m-%d}; the landlord owed the deposit and an "
                         f"itemized statement by {due:%Y-%m-%d} (21 calendar days). Miss it and the "
                         f"right to withhold is forfeited under § 1950.5(f)."),
            notes=("If the 21 days have passed with no accounting, you can demand the full deposit.",),
        )

    # ---- helpers ------------------------------------------------------------

    def _excluded_between(self, start: _dt.date, end: _dt.date) -> tuple[str, ...]:
        out: list[str] = []
        d = start + _dt.timedelta(days=1)
        while d <= end:
            if d.weekday() >= 5:
                out.append(f"{d:%a %Y-%m-%d} (weekend)")
            elif self.cal.is_holiday(d):
                out.append(f"{d:%a %Y-%m-%d} ({self.cal.holiday_name(d)})")
            d += _dt.timedelta(days=1)
        return tuple(out)
