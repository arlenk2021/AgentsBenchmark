"""Deadline-correctness benchmark — papertrail's go/no-go gate.

Runs the verified engine against the golden set (must be 100%) AND a naive
"LLM-style" baseline that does the kind of plausible-but-wrong arithmetic a general
chatbot does — counting calendar days instead of court days, ignoring holidays,
guessing on ambiguous service. The gap between the two is the empirical "why not
ChatGPT" moat, in numbers, on this exact task.

    python bench/run_benchmark.py            # human report
    python bench/run_benchmark.py --json     # machine output, exits non-zero if engine < 100%
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from papertrail.calendar_ca import CaliforniaCalendar          # noqa: E402
from papertrail.deadlines import DeadlineEngine                # noqa: E402

GOLDEN = ROOT / "bench" / "golden" / "deadlines.jsonl"


def load_golden() -> list[dict]:
    rows = []
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def _date(s):
    return _dt.date.fromisoformat(s) if s else None


def _call_engine(engine: DeadlineEngine, fn: str, args: dict):
    a = {k: (_date(v) if k in ("served", "vacated", "tenancy_start") else v)
         for k, v in args.items()}
    dl = getattr(engine, fn)(**a)
    return dl.last_day, dl.confidence


# ---- the naive baseline: what a general LLM tends to do -----------------------

def _naive_baseline(fn: str, args: dict):
    """Plausible-but-wrong: count CALENDAR days, ignore holidays, and confidently
    guess on ambiguous inputs instead of refusing. Mirrors the documented failure
    mode of general LLMs on verifiable legal questions (Stanford RegLab, 58-88%)."""
    served = _date(args.get("served") or args.get("vacated"))
    if fn == "pay_or_quit":
        return served + _dt.timedelta(days=3)              # ignores court-day exclusion
    if fn == "ud_answer":
        return served + _dt.timedelta(days=10)             # treats as 10 calendar days; no refusal
    if fn == "termination_notice":
        # guesses 30 even when occupancy is unknown or >= 1 year
        return served + _dt.timedelta(days=30)
    if fn == "deposit_return":
        return served + _dt.timedelta(days=21)             # right here by luck (pure calendar)
    return None


def run(as_json: bool = False) -> int:
    golden = load_golden()
    engine = DeadlineEngine(CaliforniaCalendar())
    eng_pass = naive_pass = 0
    details = []

    for row in golden:
        expected = _date(row["expected"])
        eng_date, conf = _call_engine(engine, row["fn"], row["args"])
        # A "needs_review" refusal is the correct answer when expected is null.
        eng_ok = (eng_date == expected) and not (expected is None and conf != "needs_review")
        naive_date = _naive_baseline(row["fn"], row["args"])
        naive_ok = naive_date == expected
        eng_pass += eng_ok
        naive_pass += naive_ok
        details.append({
            "id": row["id"], "fn": row["fn"],
            "expected": row["expected"],
            "engine": eng_date.isoformat() if eng_date else f"REFUSED({conf})",
            "engine_ok": eng_ok,
            "naive": naive_date.isoformat() if naive_date else None,
            "naive_ok": naive_ok,
        })

    n = len(golden)
    eng_acc = eng_pass / n
    naive_acc = naive_pass / n
    summary = {
        "n": n,
        "engine_accuracy": eng_acc,
        "naive_baseline_accuracy": naive_acc,
        "gate_passed": eng_acc == 1.0,
        "moat_gap": round(eng_acc - naive_acc, 3),
    }

    if as_json:
        print(json.dumps({"summary": summary, "cases": details}, indent=2))
    else:
        print("=== papertrail deadline-correctness benchmark ===\n")
        for d in details:
            mark = "PASS" if d["engine_ok"] else "FAIL"
            nmark = "ok " if d["naive_ok"] else "WRONG"
            print(f"  [{mark}] {d['id']:28} engine={d['engine']:20} | naive={str(d['naive']):12} {nmark}")
        print(f"\n  engine accuracy : {eng_acc:.0%}  ({eng_pass}/{n})")
        print(f"  naive LLM-style : {naive_acc:.0%}  ({naive_pass}/{n})  <- the 'why not ChatGPT' gap")
        print(f"  GATE: {'PASS — deadline feature may ship' if summary['gate_passed'] else 'FAIL — DO NOT SHIP the deadline feature'}")

    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    raise SystemExit(run(as_json=ap.parse_args().json))
