"""Tests for papertrail. Run: python tests/test_papertrail.py  (or pytest)."""
import datetime as _dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from papertrail import (  # noqa: E402
    CaliforniaCalendar, DeadlineEngine, classify, EvidenceLog, Entry,
    deposit_demand, assess_deposit, check_deposit_cap, cite, DISCLAIMER,
)

D = _dt.date.fromisoformat


# ---- calendar / deadlines ---------------------------------------------------

def test_court_days_skip_weekend():
    eng = DeadlineEngine()
    assert eng.pay_or_quit(D("2026-06-03")).last_day == D("2026-06-08")  # Wed -> Mon


def test_ud_excludes_juneteenth():
    eng = DeadlineEngine()
    assert eng.ud_answer(D("2026-06-15")).last_day == D("2026-06-30")


def test_ud_substituted_refuses():
    dl = DeadlineEngine().ud_answer(D("2026-06-01"), service_method="substituted")
    assert dl.last_day is None and dl.confidence == "needs_review"


def test_termination_60_for_long_tenancy():
    dl = DeadlineEngine().termination_notice(D("2026-06-01"), tenancy_start=D("2024-01-01"))
    assert dl.last_day == D("2026-07-31")


def test_termination_unknown_refuses():
    dl = DeadlineEngine().termination_notice(D("2026-06-01"))
    assert dl.last_day is None and dl.confidence == "needs_review"


def test_deposit_21_calendar():
    assert DeadlineEngine().deposit_return(D("2026-06-01")).last_day == D("2026-06-22")


def test_observed_holiday_shift():
    cal = CaliforniaCalendar()
    # Jul 4 2026 is Saturday -> observed Friday Jul 3.
    assert cal.is_holiday(D("2026-07-03"))
    assert not cal.is_court_day(D("2026-07-03"))


# ---- classifier -------------------------------------------------------------

def test_classify_pay_or_quit():
    c = classify("THREE-DAY NOTICE TO PAY RENT OR QUIT. You have past due rent.")
    assert c.notice_type == "pay_or_quit" and c.deadline_fn == "pay_or_quit"


def test_classify_ud_overrides():
    c = classify("SUMMONS - UNLAWFUL DETAINER. You must file a response within 5 days.")
    assert c.notice_type == "unlawful_detainer" and c.deadline_fn == "ud_answer"


def test_classify_unknown_is_safe():
    c = classify("Happy birthday, here is a cake recipe.")
    assert c.notice_type == "unknown" and c.deadline_fn is None


# ---- evidence ---------------------------------------------------------------

def test_evidence_integrity_detects_tampering():
    clock = _dt.datetime(2026, 6, 1, 12, 0, tzinfo=_dt.timezone.utc)
    log = EvidenceLog("test")
    log.add(Entry.create("condition", "No hot water", "2026-05-20", clock=clock))
    ok, bad = log.integrity()
    assert ok and not bad
    # Tamper: replace summary, keep old hash.
    e = log.entries[0]
    log.entries[0] = Entry(e.kind, "Different claim", e.occurred_on, e.captured_at,
                           e.detail, e.attachment, e.content_hash)
    ok, bad = log.integrity()
    assert not ok and bad


def test_evidence_packet_renders():
    clock = _dt.datetime(2026, 6, 1, 12, 0, tzinfo=_dt.timezone.utc)
    log = EvidenceLog("Smith v. Stranda")
    log.add(Entry.create("communication", "Emailed landlord re: leak", "2026-05-21", clock=clock))
    pkt = log.render_packet()
    assert "Evidence Packet" in pkt and "VERIFIED" in pkt


# ---- deposit ----------------------------------------------------------------

def test_deposit_cap_over():
    chk = check_deposit_cap(monthly_rent=2000, deposit_charged=4000)
    assert chk.over_cap and chk.lawful_max == 2000


def test_deposit_cap_small_landlord_ok():
    chk = check_deposit_cap(monthly_rent=2000, deposit_charged=4000, small_landlord=True)
    assert not chk.over_cap


def test_deposit_service_member_overrides_small_landlord():
    chk = check_deposit_cap(monthly_rent=2000, deposit_charged=4000,
                            small_landlord=True, service_member=True)
    assert chk.over_cap and chk.lawful_max == 2000


def test_deposit_overdue_exposure_with_bad_faith():
    case = assess_deposit(monthly_rent=2500, deposit=2500, vacated=D("2026-05-01"),
                          today=D("2026-06-11"), bad_faith=True)
    assert case.overdue
    assert case.exposure.base_recoverable == 2500
    assert case.exposure.statutory_damages_max == 5000
    assert case.exposure.total_max == 7500
    assert case.exposure.small_claims_ok  # 7500 < 12500


def test_deposit_not_yet_due():
    case = assess_deposit(monthly_rent=2500, deposit=2500, vacated=D("2026-06-05"),
                          today=D("2026-06-11"))
    assert not case.overdue and case.exposure.base_recoverable == 0.0


# ---- letters / UPL-safety ---------------------------------------------------

def test_demand_letter_is_sourced_and_disclaimed():
    eng = DeadlineEngine()
    dl = eng.deposit_return(D("2026-05-01"))
    letter = deposit_demand(tenant="Arlen K", landlord="Stranda Apts", address="123 Berkeley Way",
                            deposit_amount=2500, vacated=D("2026-05-01"), deadline=dl,
                            bad_faith=True, today=D("2026-06-11"))
    rendered = letter.render()
    assert "§ 1950.5" in rendered or "1950.5" in rendered
    assert "not a law firm" in DISCLAIMER and DISCLAIMER in rendered
    assert "civ_1950_5" in letter.citations_used


def test_every_citation_resolves():
    for key in ("ccp_1161", "ccp_1167", "civ_1946_1", "civ_1950_5", "civ_1950_5_l",
                "ab_12", "ab_2801", "ccp_116_221", "civ_1942_5", "ab_2347"):
        c = cite(key)
        assert c.url.startswith("http") and c.verified_on


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
