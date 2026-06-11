"""seatwatch — course-seat availability watcher.

Honest framing (from the market analysis): seatwatch's moat is NOT anti-hallucination —
it's real-time scraping + state-diffing + push notification, which a chat LLM genuinely
cannot do, but which Coursicle already owns at ~2M students. So this is built lean and
correctly: a pluggable source adapter, a deterministic seat-state diff, and a
transport-agnostic notifier. The defensible angle, if any, is depth on one registrar
(e.g. Berkeley CalCentral: waitlist position, section-swap logic) — modeled here as the
adapter interface, not assumed.

No network code lives here; a real adapter implements `SeatSource.snapshot()`. That keeps
the diff/notify logic unit-testable and the scraping concerns isolated.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class SeatState(str, Enum):
    OPEN = "open"
    WAITLIST = "waitlist"
    CLOSED = "closed"


@dataclass(frozen=True)
class Section:
    course: str            # e.g. "COMPSCI 161"
    section_id: str        # e.g. "001" / CCN
    title: str
    state: SeatState
    open_seats: int
    waitlist_len: int
    term: str

    @property
    def key(self) -> str:
        return f"{self.term}:{self.course}:{self.section_id}"


class SeatSource(abc.ABC):
    """A registrar adapter. Real implementations scrape CalCentral / SIS; the contract is
    just 'give me the current sections for these courses'."""

    @abc.abstractmethod
    def snapshot(self, courses: Iterable[str], term: str) -> list[Section]:
        ...


# ---- the diff: where the value is ---------------------------------------------

class TransitionKind(str, Enum):
    OPENED = "opened"                  # closed/waitlist -> open  (the alert users want)
    SEAT_FREED = "seat_freed"          # open_seats increased
    WAITLIST_SHRANK = "waitlist_shrank"
    CLOSED = "closed"                  # open/waitlist -> closed
    NEW = "new"                        # first time seen


@dataclass(frozen=True)
class Transition:
    section_key: str
    course: str
    kind: TransitionKind
    before: SeatState | None
    after: SeatState
    detail: str


def diff_snapshots(prev: list[Section], curr: list[Section]) -> list[Transition]:
    """Deterministic state diff between two snapshots. This is the core logic a
    notification fires on — kept pure so it's trivially testable."""
    prev_by = {s.key: s for s in prev}
    out: list[Transition] = []
    for s in curr:
        before = prev_by.get(s.key)
        if before is None:
            out.append(Transition(s.key, s.course, TransitionKind.NEW, None, s.state,
                                  f"now tracking {s.course} {s.section_id} ({s.state.value})"))
            continue
        if before.state is not SeatState.OPEN and s.state is SeatState.OPEN:
            out.append(Transition(s.key, s.course, TransitionKind.OPENED, before.state, s.state,
                                  f"{s.course} {s.section_id} OPENED — {s.open_seats} seat(s)"))
        elif s.state is SeatState.OPEN and s.open_seats > before.open_seats:
            out.append(Transition(s.key, s.course, TransitionKind.SEAT_FREED, before.state, s.state,
                                  f"{s.course} {s.section_id}: {before.open_seats} -> {s.open_seats} seats"))
        elif s.state is SeatState.CLOSED and before.state is not SeatState.CLOSED:
            out.append(Transition(s.key, s.course, TransitionKind.CLOSED, before.state, s.state,
                                  f"{s.course} {s.section_id} closed"))
        elif (s.state is SeatState.WAITLIST and before.state is SeatState.WAITLIST
              and s.waitlist_len < before.waitlist_len):
            out.append(Transition(s.key, s.course, TransitionKind.WAITLIST_SHRANK, before.state, s.state,
                                  f"{s.course} {s.section_id} waitlist {before.waitlist_len} -> {s.waitlist_len}"))
    return out


# ---- notification: transport-agnostic -----------------------------------------

class Notifier(abc.ABC):
    @abc.abstractmethod
    def send(self, transition: Transition) -> None:
        ...


@dataclass
class CollectingNotifier(Notifier):
    """Test/default notifier that just records what would be sent. Real notifiers wrap
    push/SMS/email; the watch loop doesn't care which."""
    sent: list[Transition] = field(default_factory=list)

    def send(self, transition: Transition) -> None:
        self.sent.append(transition)


# Which transitions are worth waking a student for. Configurable; defaults to the ones
# that matter at enrollment time.
ALERT_ON = {TransitionKind.OPENED, TransitionKind.SEAT_FREED, TransitionKind.WAITLIST_SHRANK}


@dataclass
class Watcher:
    source: SeatSource
    notifier: Notifier
    term: str
    courses: list[str]
    alert_on: set[TransitionKind] = field(default_factory=lambda: set(ALERT_ON))
    _last: list[Section] = field(default_factory=list)

    def poll(self) -> list[Transition]:
        """One polling cycle: snapshot, diff against last, notify on alert-worthy changes."""
        curr = self.source.snapshot(self.courses, self.term)
        transitions = diff_snapshots(self._last, curr)
        for t in transitions:
            if t.kind in self.alert_on:
                self.notifier.send(t)
        self._last = curr
        return transitions
