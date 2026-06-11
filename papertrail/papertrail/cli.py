"""`python -m papertrail <command>` — the kit, end to end.

  classify   identify a notice you were handed (paste its text)
  deadline   compute a verified deadline for a known notice type
  deposit    assess a security-deposit return (cap, deadline, dollar exposure)
  demand     generate a sourced § 1950.5 deposit-demand letter (your voice)
  citations  print the statute registry (and flag stale entries)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys

from .calendar_ca import CaliforniaCalendar
from .deadlines import DeadlineEngine
from .classify import classify
from .deposit import assess_deposit
from .letters import deposit_demand
from .citations import CITATIONS, stale_citations


def _d(s: str) -> _dt.date:
    return _dt.date.fromisoformat(s)


def cmd_classify(a) -> int:
    text = a.text or sys.stdin.read()
    c = classify(text)
    print(f"Notice type : {c.notice_type}  (confidence {c.confidence})")
    print(f"Deadline fn : {c.deadline_fn or '—'}")
    print(f"Guidance    : {c.guidance}")
    if c.deadline_fn and a.served:
        eng = DeadlineEngine(CaliforniaCalendar())
        fn = getattr(eng, c.deadline_fn)
        try:
            dl = fn(_d(a.served)) if c.deadline_fn != "termination_notice" else fn(_d(a.served))
            print("\n" + dl.render())
        except TypeError:
            print("\n(Provide --served and tenancy facts to compute this deadline.)")
    return 0


def cmd_deadline(a) -> int:
    eng = DeadlineEngine(CaliforniaCalendar())
    if a.kind == "pay_or_quit":
        dl = eng.pay_or_quit(_d(a.served))
    elif a.kind == "ud_answer":
        dl = eng.ud_answer(_d(a.served), service_method=a.service_method)
    elif a.kind == "termination":
        dl = eng.termination_notice(_d(a.served),
                                    tenancy_start=_d(a.tenancy_start) if a.tenancy_start else None)
    elif a.kind == "deposit_return":
        dl = eng.deposit_return(_d(a.served))
    else:
        print(f"unknown kind '{a.kind}'"); return 2
    print(dl.render())
    return 0


def cmd_deposit(a) -> int:
    case = assess_deposit(
        monthly_rent=a.rent, deposit=a.deposit, vacated=_d(a.vacated),
        today=_d(a.today) if a.today else None, bad_faith=a.bad_faith,
        small_landlord=a.small_landlord, service_member=a.service_member,
    )
    print(case.render())
    return 0


def cmd_demand(a) -> int:
    eng = DeadlineEngine(CaliforniaCalendar())
    dl = eng.deposit_return(_d(a.vacated))
    letter = deposit_demand(
        tenant=a.tenant, landlord=a.landlord, address=a.address,
        deposit_amount=a.deposit, vacated=_d(a.vacated), deadline=dl,
        bad_faith=a.bad_faith, today=_d(a.today) if a.today else None,
    )
    print(letter.render())
    return 0


def cmd_citations(a) -> int:
    for c in CITATIONS.values():
        print(c.render() + "\n")
    stale = stale_citations(_dt.date.today().isoformat())
    if stale:
        print("STALE (re-verify):", ", ".join(c.key for c in stale))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="papertrail", description="CA renter deadline/evidence/letter kit")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="identify a notice")
    c.add_argument("--text"); c.add_argument("--served")
    c.set_defaults(func=cmd_classify)

    d = sub.add_parser("deadline", help="compute a verified deadline")
    d.add_argument("kind", choices=["pay_or_quit", "ud_answer", "termination", "deposit_return"])
    d.add_argument("--served", required=True)
    d.add_argument("--service-method", default="personal")
    d.add_argument("--tenancy-start")
    d.set_defaults(func=cmd_deadline)

    dp = sub.add_parser("deposit", help="assess a deposit return")
    dp.add_argument("--rent", type=float, required=True)
    dp.add_argument("--deposit", type=float, required=True)
    dp.add_argument("--vacated", required=True)
    dp.add_argument("--today")
    dp.add_argument("--bad-faith", action="store_true")
    dp.add_argument("--small-landlord", action="store_true")
    dp.add_argument("--service-member", action="store_true")
    dp.set_defaults(func=cmd_deposit)

    dm = sub.add_parser("demand", help="generate a deposit-demand letter")
    dm.add_argument("--deposit", type=float, required=True)
    dm.add_argument("--vacated", required=True)
    dm.add_argument("--tenant"); dm.add_argument("--landlord"); dm.add_argument("--address")
    dm.add_argument("--today"); dm.add_argument("--bad-faith", action="store_true")
    dm.set_defaults(func=cmd_demand)

    ct = sub.add_parser("citations", help="print the statute registry")
    ct.set_defaults(func=cmd_citations)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)
