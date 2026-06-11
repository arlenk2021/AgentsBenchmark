# papertrail

A California renter's **deadline + evidence + letter** kit. The flagship of four
side-project candidates (see the product analysis), built on one verified core and
designed against the two failure modes that have sunk similar products: **legal
hallucination** and **unauthorized practice of law (UPL)**.

`depositback` (security-deposit recovery) is folded in as the calm, high-volume
top-of-funnel module — same statute, same engine, same user.

## Why this design

- **Every legal fact is sourced.** `citations.py` is the single registry; nothing reaches
  a user without a verifiable statute cite and a `verified_on` date. This is the
  anti-DoNotPay choice made structural.
- **The deadline engine is gated by a benchmark.** `bench/run_benchmark.py` scores the
  engine against hand-verified CA scenarios. It must be **100%** or the deadline feature
  doesn't ship. A naive LLM-style baseline scores **36%** on the same set — the "why not
  ChatGPT" moat, in numbers.
- **UPL-safe by construction.** Letters are generated in the user's own voice for them to
  send themselves, with a scope disclaimer; the engine refuses (`needs_review`) on
  ambiguous inputs rather than assert a wrong date. See [MARKET.md](MARKET.md).

## Quickstart

```bash
cd papertrail
python tests/test_papertrail.py        # 19 tests
python bench/run_benchmark.py          # the go/no-go deadline gate (engine 100% vs naive 36%)

# compute a verified deadline
python -m papertrail deadline ud_answer --served 2026-06-15 --service-method personal
python -m papertrail deadline pay_or_quit --served 2026-07-02

# assess a deposit and generate a sourced demand letter (your voice)
python -m papertrail deposit --rent 2500 --deposit 2500 --vacated 2026-05-01 --today 2026-06-11 --bad-faith
python -m papertrail demand  --deposit 2500 --vacated 2026-05-01 --tenant "Your Name" --bad-faith

# identify a notice you were handed
python -m papertrail classify --text "THREE-DAY NOTICE TO PAY RENT OR QUIT ..."

# inspect the statute registry (flags stale entries for re-verification)
python -m papertrail citations
```

## Layout

```
papertrail/
├── papertrail/
│   ├── citations.py     statute registry — single source of truth, with verified_on dates
│   ├── calendar_ca.py   CA judicial calendar; court-day vs calendar-day arithmetic (load-bearing)
│   ├── deadlines.py     the verified deadline engine (3-day, UD answer, 30/60-day, deposit)
│   ├── classify.py      transparent, rule-based notice-type classifier
│   ├── evidence.py      hash-attested evidence log -> court-ready packet
│   ├── letters.py       UPL-safe, sourced letter generator (user's voice + disclaimer)
│   ├── deposit.py       depositback: cap check + return deadline + dollar exposure
│   └── cli.py           python -m papertrail ...
├── bench/               the deadline-correctness go/no-go gate + golden set
├── tests/
├── MARKET.md            verified legal facts (with corrections), sizing, UPL analysis
└── README.md
```

> **Disclaimer:** papertrail is not a law firm and does not provide legal advice. It
> organizes your facts and the cited statutes into materials you act on yourself. Verify
> citations and consult a tenant attorney or legal-aid clinic for advice.
