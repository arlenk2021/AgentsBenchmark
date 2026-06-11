"""California judicial calendar — court-day vs. calendar-day arithmetic.

This is the load-bearing, dangerous-if-wrong module. A wrong deadline is the one
failure that loses a user their home, so the rules here are deliberately explicit and
covered by the benchmark in `bench/` at 100% before any deadline feature ships.

Two kinds of counting appear in CA tenancy law:
  * CALENDAR days — every day counts (30/60-day terminations; the §1950.5 21-day clock).
  * COURT days   — Saturdays, Sundays, and judicial holidays are EXCLUDED (the 3-day
                   pay-or-quit notice under CCP §1161; the 10-day UD answer under §1167).

Judicial holidays are set by Cal. Gov. Code §§ 6700–6701 and CCP § 135. We encode the
fixed-date and floating holidays plus the "observed" rule (a holiday on Saturday is
observed the preceding Friday; on Sunday, the following Monday — CCP § 12a / § 135).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    """The nth (1-based) given weekday of a month. weekday: Mon=0..Sun=6."""
    d = _dt.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + _dt.timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> _dt.date:
    """The last given weekday of a month."""
    if month == 12:
        nxt = _dt.date(year + 1, 1, 1)
    else:
        nxt = _dt.date(year, month + 1, 1)
    d = nxt - _dt.timedelta(days=1)
    return d - _dt.timedelta(days=(d.weekday() - weekday) % 7)


def _fixed_holidays(year: int) -> dict[_dt.date, str]:
    """California state/judicial holidays for a year, BEFORE weekend-observation shift."""
    h: dict[_dt.date, str] = {
        _dt.date(year, 1, 1): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",       # 3rd Mon Jan
        _nth_weekday(year, 2, 0, 3): "Presidents' Day",                  # 3rd Mon Feb
        _last_weekday(year, 5, 0): "Memorial Day",                       # last Mon May
        _dt.date(year, 6, 19): "Juneteenth",                            # CA judicial holiday since 2023
        _dt.date(year, 7, 4): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",                        # 1st Mon Sep
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",                # 4th Thu Nov
        _dt.date(year, 11, 11): "Veterans Day",
        _dt.date(year, 12, 25): "Christmas Day",
    }
    # Day after Thanksgiving is a CA judicial holiday.
    h[_nth_weekday(year, 11, 3, 4) + _dt.timedelta(days=1)] = "Day after Thanksgiving"
    return h


def _observed(d: _dt.date) -> _dt.date:
    """Weekend-observation shift (CCP § 12a / § 135): a holiday falling on Saturday is
    observed the preceding Friday; on Sunday, the following Monday."""
    if d.weekday() == 5:        # Saturday
        return d - _dt.timedelta(days=1)
    if d.weekday() == 6:        # Sunday
        return d + _dt.timedelta(days=1)
    return d


class CaliforniaCalendar:
    """Holiday-aware court-day calculator. Stateless except for a per-year holiday cache."""

    def __init__(self) -> None:
        self._cache: dict[int, set[_dt.date]] = {}

    def holidays(self, year: int) -> set[_dt.date]:
        if year not in self._cache:
            observed: set[_dt.date] = set()
            for d in _fixed_holidays(year):
                observed.add(_observed(d))
            # New Year's Day of the following year can be observed on Dec 31 of this year.
            observed.add(_observed(_dt.date(year + 1, 1, 1)))
            self._cache[year] = observed
        return self._cache[year]

    def is_holiday(self, d: _dt.date) -> bool:
        return d in self.holidays(d.year)

    def is_court_day(self, d: _dt.date) -> bool:
        """A court day is any weekday that is not a judicial holiday."""
        return d.weekday() < 5 and not self.is_holiday(d)

    def holiday_name(self, d: _dt.date) -> str | None:
        for raw, name in _fixed_holidays(d.year).items():
            if _observed(raw) == d:
                return name
        if _observed(_dt.date(d.year + 1, 1, 1)) == d:
            return "New Year's Day (observed)"
        return None

    # ---- counting -----------------------------------------------------------

    def add_court_days(self, start: _dt.date, n: int) -> _dt.date:
        """Return the date n court days AFTER `start`. Counting begins the day after
        `start` (the service date is day 0), per CCP § 1161 / § 1167 practice.

        If the resulting day would be a weekend/holiday the statutes already exclude it,
        so the returned date is always itself a court day (the last day to act)."""
        if n < 1:
            raise ValueError("court-day deadlines count at least 1 day")
        d = start
        counted = 0
        while counted < n:
            d += _dt.timedelta(days=1)
            if self.is_court_day(d):
                counted += 1
        return d

    def add_calendar_days(self, start: _dt.date, n: int) -> _dt.date:
        """Return the date n calendar days after `start` (service date is day 0).

        Per CCP § 12 / § 12a, if the last day lands on a weekend or holiday, the deadline
        rolls forward to the next court day. This roll-forward applies to filing/response
        deadlines; it does NOT extend a landlord's own statutory duty date (e.g. the
        §1950.5 21-day return clock is a hard calendar count — see deadlines.py)."""
        if n < 1:
            raise ValueError("calendar-day deadlines count at least 1 day")
        d = start + _dt.timedelta(days=n)
        return d

    def roll_forward_to_court_day(self, d: _dt.date) -> _dt.date:
        """Advance `d` to the next court day if it falls on a weekend/holiday."""
        while not self.is_court_day(d):
            d += _dt.timedelta(days=1)
        return d


@dataclass(frozen=True)
class DayCount:
    """A computed span, with enough provenance to explain it to a user or a court."""
    start: _dt.date
    end: _dt.date
    mode: str                 # "court" | "calendar"
    skipped: tuple[str, ...]  # human-readable list of days excluded (court mode)
