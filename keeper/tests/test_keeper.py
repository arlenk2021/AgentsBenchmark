"""Tests for keeper. Run: python tests/test_keeper.py  (or pytest)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from keeper import RegDB, can_i_keep, Verdict  # noqa: E402

DB = RegDB.load_dir(ROOT / "data")


def test_halibut_legal_north():
    d = can_i_keep(DB, species="halibut", size_in=24, region="north_of_point_sur")
    assert d.verdict is Verdict.KEEP


def test_halibut_undersize_releases():
    d = can_i_keep(DB, species="halibut", size_in=20, region="north_of_point_sur")
    assert d.verdict is Verdict.RELEASE and "minimum" in d.reason


def test_halibut_bag_limit_north_is_two():
    d = can_i_keep(DB, species="halibut", size_in=24, region="north_of_point_sur", already_kept=2)
    assert d.verdict is Verdict.RELEASE and "bag limit" in d.reason


def test_halibut_bag_limit_south_is_five():
    d = can_i_keep(DB, species="halibut", size_in=24, region="south_of_point_sur", already_kept=2)
    assert d.verdict is Verdict.KEEP  # south allows 5


def test_abalone_closed():
    d = can_i_keep(DB, species="abalone")
    assert d.verdict is Verdict.CLOSED


def test_salmon_frequently_closed_is_cautious():
    d = can_i_keep(DB, species="king salmon", size_in=30)
    assert d.verdict is Verdict.CLOSED and d.confidence == "verify"


def test_unknown_species_refuses():
    d = can_i_keep(DB, species="unobtainium fish")
    assert d.verdict is Verdict.UNKNOWN


def test_size_required_but_missing_releases():
    d = can_i_keep(DB, species="halibut", region="north_of_point_sur")  # no size
    assert d.verdict is Verdict.RELEASE and "measure" in " ".join(d.warnings).lower()


def test_bass_no_min_size_keeps():
    d = can_i_keep(DB, species="largemouth bass")
    assert d.verdict is Verdict.KEEP  # statewide default 5/day, no min size


def test_every_rule_has_citation_and_verified_date():
    for sp in DB.species:
        for r in sp.rules:
            assert r.citation and r.verified_on


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
