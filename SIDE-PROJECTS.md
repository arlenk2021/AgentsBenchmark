# Four human-facing side projects — build index

Built from the product analysis (June 11, 2026). All four are implemented as runnable,
tested Python; every legal/regulatory fact is sourced and was verified **2026-06-11**.
Ranking and rationale follow the analysis, with corrections noted in `papertrail/MARKET.md`.

| Project | Verdict | What's built | Tests |
|---|---|---|---|
| **[papertrail](papertrail/)** | **Flagship** | CA renter deadline engine + evidence packet + UPL-safe sourced letters; **deadline benchmark gate** (engine 100% vs naive LLM-style 36%) | 19 + 11 bench |
| **[depositback](papertrail/papertrail/deposit.py)** | **Folded into papertrail** | §1950.5 cap check + 21-day deadline + 2× exposure + demand letter, as papertrail's calm top-of-funnel | (in papertrail) |
| **[keeper](keeper/)** | **Second** | Offline, provenance-tracked CA fishing-reg DB + "can I keep this?" engine (KEEP/RELEASE/CLOSED) | 10 |
| **[seatwatch](seatwatch/)** | **Lean / breadth** | Real-time seat-diff + notify core behind a registrar adapter contract; honestly framed as a scraping moat | 6 |

## The through-line

Three of the four are the same engineering thesis: **a messy authoritative source →
verified structured data → an honest, uncertainty-aware answer at the moment of need.**

- papertrail/depositback: CA statutes → deadline engine → "is this date right?" (gated at
  100% because a wrong deadline loses a home).
- keeper: CDFW PDFs → offline reg DB → "can I keep this?" (biased to RELEASE because a
  wrong keep is a fine).
- seatwatch: registrar pages → seat-state diff → "did a seat open?" (the one where the
  moat is scraping infra, not correctness — and the category is already won).

## The two failure modes designed against (papertrail)

1. **Legal hallucination** — made empirical by `papertrail/bench/`: general LLMs are
   documented at 58–88% hallucination on verifiable legal questions (Stanford RegLab);
   the verified engine is 100% on the same task where a naive baseline is 64% wrong.
2. **Unauthorized practice of law** — the bigger existential risk for a solo build;
   addressed structurally (user's-voice letters, statute citations, scope disclaimers,
   refuse-on-ambiguity). See `papertrail/MARKET.md`.

## Run everything

```bash
python papertrail/tests/test_papertrail.py && python papertrail/bench/run_benchmark.py
python keeper/tests/test_keeper.py
python seatwatch/tests/test_seatwatch.py
```

Each project is standalone (its own README, tests, CLI). None of this is legal, financial,
or regulatory advice; the products organize sourced information for a person to act on
themselves.
