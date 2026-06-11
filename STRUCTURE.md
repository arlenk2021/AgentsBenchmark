# Repo structure

```
wrodium-bench/
├── README.md                  Stage-by-stage map to the playbook
├── STRUCTURE.md               this file
├── pyproject.toml             package + `wrodium` console script + pytest config
│
├── wrodium/                   the framework
│   ├── util.py                Report / Issue / Severity — the gate spine; jsonl + hashing
│   ├── cli.py                 `python -m wrodium <cmd>` — drives every stage
│   ├── __main__.py
│   │
│   ├── schema/                specs the operator authors
│   │   ├── proposal.py        Stage 0 — 5/5 scorecard + insider reject
│   │   ├── primitive.py       Stage 1+2 — required blocks, ToS gate, the three rules
│   │   └── golden.py          Stage 3 — row schema, verified fields, holdout floor, strata split
│   │
│   ├── adapters/              Stage 4 — vendor transport
│   │   ├── base.py            VendorAdapter contract: capabilities, error mapping, raw persistence
│   │   ├── conformance.py     the merge gate (`conformance_test`)
│   │   └── mock.py            PerfectMockAdapter / FaultyMockAdapter (dry run + --demo)
│   │
│   ├── scoring/               Stage 5 — deterministic, published-verbatim
│   │   ├── states.py          ResultState (correct/incorrect/no_coverage/blocked/timeout/fetch_failed)
│   │   ├── engine.py          match_* primitives + score_cell (docstrings = methodology page)
│   │   └── metrics.py         aggregates: accuracy, coverage, cost_per_correct, overfit_gap (DASH = None)
│   │
│   ├── snapshot/              Stage 6 — run + mint
│   │   ├── preflight.py       hard gate: ToS, cost tables non-null, holdout ≥25%
│   │   └── run.py             dry_run (fidelity 1.0), run_snapshot, immutable id minting
│   │
│   └── publish/               Stage 8 — agent + human surfaces
│       ├── llms_txt.py        full leaderboard markdown (dash legend, exclusions, snapshot id)
│       ├── json_api.py        snapshot + index payloads
│       ├── openapi.py         OpenAPI 3.1 for the JSON routes
│       └── mcp_server.py      .well-known/mcp.json + recommend()/query() (BenchRegistry)
│
├── primitives/
│   ├── web_extraction.yaml    the canonical template (Stage 2 says "copy this")
│   └── _proposals/
│       └── kyb_registry.example.yaml   a passing Stage-0 proposal
│
├── golden/
│   ├── web_extraction/
│   │   └── rows.sample.jsonl  12-row stratified sample (public split)
│   └── planted_pages/
│       └── PROTOCOL.md        freshness 24-cell matrix + authoritative T0 rules
│
└── tests/
    └── test_framework.py      17 gate tests; runnable via pytest or directly
```

## What is intentionally left as an extension point

This is the spine, not a finished product. The seams a deployed engineer fills per
playbook stage:

- **Real adapters** subclass `VendorAdapter` (implement `capabilities()` + `_invoke()`);
  `run_conformance()` is their merge gate. The mocks show the shape.
- **The judged-metric path** (Stage 5, <30% of items) — `scoring.method: judged` is
  validated for a pinned model/version/prompt, but `judge.py` is left to add when a
  primitive actually needs it.
- **Drift + lag crawlers** (Stage 9) — `page_hash` is already on every golden row and
  in the planted-pages manifest; the scheduler that diffs hashes and files
  re-verification tickets is ops wiring, not framework.
- **A web server** — `publish/json_api.py` and `mcp_server.py` are framework-agnostic
  data/logic; wrap them in FastAPI / a Vercel function / FastMCP to serve.
