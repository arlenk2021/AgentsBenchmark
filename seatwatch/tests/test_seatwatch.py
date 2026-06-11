"""Tests for seatwatch. Run: python tests/test_seatwatch.py  (or pytest)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seatwatch import (  # noqa: E402
    SeatState, Section, SeatSource, CollectingNotifier, TransitionKind,
    diff_snapshots, Watcher,
)


def _sec(course, sid, state, open_seats=0, wl=0, term="2026-fall"):
    return Section(course, sid, f"{course} title", state, open_seats, wl, term)


class ScriptedSource(SeatSource):
    """A source that replays a list of predefined snapshots, one per poll."""
    def __init__(self, snapshots):
        self._snaps = list(snapshots)
        self._i = 0

    def snapshot(self, courses, term):
        snap = self._snaps[min(self._i, len(self._snaps) - 1)]
        self._i += 1
        return snap


def test_diff_detects_open():
    prev = [_sec("CS 161", "001", SeatState.CLOSED)]
    curr = [_sec("CS 161", "001", SeatState.OPEN, open_seats=1)]
    ts = diff_snapshots(prev, curr)
    assert len(ts) == 1 and ts[0].kind is TransitionKind.OPENED


def test_diff_seat_freed():
    prev = [_sec("CS 161", "001", SeatState.OPEN, open_seats=1)]
    curr = [_sec("CS 161", "001", SeatState.OPEN, open_seats=3)]
    assert diff_snapshots(prev, curr)[0].kind is TransitionKind.SEAT_FREED


def test_diff_waitlist_shrank():
    prev = [_sec("CS 161", "001", SeatState.WAITLIST, wl=10)]
    curr = [_sec("CS 161", "001", SeatState.WAITLIST, wl=7)]
    assert diff_snapshots(prev, curr)[0].kind is TransitionKind.WAITLIST_SHRANK


def test_diff_new_section():
    assert diff_snapshots([], [_sec("CS 161", "001", SeatState.CLOSED)])[0].kind is TransitionKind.NEW


def test_no_spurious_transition_when_unchanged():
    s = [_sec("CS 161", "001", SeatState.CLOSED)]
    assert diff_snapshots(s, s) == []


def test_watcher_only_alerts_on_configured_kinds():
    snaps = [
        [_sec("CS 161", "001", SeatState.CLOSED)],            # poll 1: NEW (not alerted)
        [_sec("CS 161", "001", SeatState.OPEN, open_seats=2)],# poll 2: OPENED (alerted)
        [_sec("CS 161", "001", SeatState.CLOSED)],            # poll 3: CLOSED (not alerted)
    ]
    notifier = CollectingNotifier()
    w = Watcher(ScriptedSource(snaps), notifier, term="2026-fall", courses=["CS 161"])
    w.poll(); w.poll(); w.poll()
    kinds = [t.kind for t in notifier.sent]
    assert kinds == [TransitionKind.OPENED]  # NEW and CLOSED are not alert-worthy by default


if __name__ == "__main__":
    import traceback
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in fns:
        try:
            fn(); print(f"  PASS {name}"); passed += 1
        except Exception:
            print(f"  FAIL {name}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
