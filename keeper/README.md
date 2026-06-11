# keeper — "Can I keep this fish?"

Offline, verified California fishing regulations. The most defensible **non-legal** of
the four candidates: structured, provenance-tracked regulatory data over a ~1.075M-angler
CA resident base. The moat is exactly what a chatbot can't do — **current** rules,
**micro-zone** specific, with **no signal** at the lake.

## Why it's defensible

- **Offline-first.** The DB is bundled JSON; lookups need no network. Point of need is on
  the water with no bars.
- **Provenance on every rule.** Each rule carries a CDFW/Title-14 citation and a
  `verified_on` date. Stale rules (fishing regs change annually) are surfaced, not
  silently trusted — the same drift discipline as a benchmark golden set.
- **Biased toward RELEASE.** A wrong "keep" is a fine ($100–$1,000 first offense; far
  more for abalone/trophy). Ambiguous inputs (no measurement, unknown region, stale rule)
  never return "keep".

## Quickstart

```bash
cd keeper
python tests/test_keeper.py

python -m keeper halibut --size 20 --region north_of_point_sur   # RELEASE (under 22")
python -m keeper halibut --size 24 --region south_of_point_sur --kept 3   # KEEP (limit 5)
python -m keeper abalone                                          # CLOSED since 2018
python -m keeper "king salmon" --size 30                          # CLOSED (verify in-season)
```

## Layout

```
keeper/
├── keeper/
│   ├── regdb.py    messy CDFW source -> verified structured DB loader (offline)
│   ├── decide.py   the can_i_keep decision engine (KEEP/RELEASE/CLOSED/UNKNOWN)
│   └── __main__.py field CLI
├── data/           verified rule sets (ca_marine.json, ca_freshwater.json)
└── tests/
```

Data verified 2026-06-11 against CDFW. This is a portfolio core, not legal/regulatory
advice — confirm against current CDFW regulations before keeping any catch.
