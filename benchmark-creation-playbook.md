# How to Create a Wrodium Benchmark — Operator's Playbook

**v1.0 · June 2026 · Companion to the `wrodium-bench` repo**

This is the repeatable process for taking any benchmark idea ("score vendors of X for agentic consumers") from zero to a published, agent-consumable leaderboard. Each section is a stage gate: don't advance until the exit criteria are met. Owner key: **FDE** = deployed engineer, **INT** = intern track, **F** = founder call.

---

## Stage 0 — Qualify the primitive (½ day · F + FDE)

A benchmark is worth building only if it scores ≥3 of 5:

| Criterion | Test |
|---|---|
| Deterministic truth (T1/T2) | Can a script, registry, or page-we-control verify every answer? If truth needs an LLM judge for >30% of items, defer. If truth needs insiders (intent, traffic, revenue) — reject. |
| Agents are buyers | Do Claude Code / Codex / LangChain workflows select this vendor category mid-task? (Proxy: does the category appear in agent framework docs/tool lists?) |
| Freshness is scoreable | Is there an objective event clock (filing date, publish time, careers-page delta) to measure lag against? |
| ≥4 vendors with public APIs | Fewer than 4 makes a matrix, not a market. |
| Wrodium leverage | Reuses an existing cohort/ingester/crawler, or feeds GEO lead-gen. |

**Exit artifact:** one-paragraph rationale + the 5-row scorecard, committed to `primitives/_proposals/`.

**Decision record:** name the leaderboard's *consumer task(s)* now (e.g. `page_extraction`, `fresh_content_monitor`) — metrics get chosen to serve the task, never the reverse.

---

## Stage 1 — Legal & ToS gate (2–4 days · F, blocks everything)

Per vendor, complete this checklist before any adapter code exists:

```
[ ] ToS reviewed for: benchmarking/comparison clauses, automated-access
    clauses, publication restrictions, data-redistribution limits
[ ] Pricing page archived (date-stamped PDF) — pins the plan we'll bill
[ ] Plan selected: cheapest published plan that exposes the capability
[ ] Verdict recorded in primitive YAML: cleared | static_rubric_only | excluded
[ ] If excluded: one-line public reason drafted (mirrors OpenFunnel's
    "not surveyed" pattern — honesty about exclusions builds trust)
```

Golden-source legality (once per source, not per vendor):
- Government registries (EDGAR, NPI, Companies House, license boards): cleared by default — log the terms URL.
- Public ATS JSON endpoints: check per board.
- Never LinkedIn-scraped truth. Never redistributed Crunchbase/PitchBook data.
- EU personal data: company-level only unless counsel signs off.

**Exit criteria:** every vendor row in the YAML has a non-`pending_review` status; snapshot preflight will hard-fail otherwise (already enforced in `snapshot/run.py`).

---

## Stage 2 — Write the primitive spec (½ day · FDE)

Copy `primitives/web_extraction.yaml` as the template. Required blocks: `task_shapes`, `golden_sources`, `cohort` (size + strata + 70/30 split), `vendors` (with ToS status + pinned plan), `scoring` (method + match rules + result states), `metrics`, `regions`.

Three rules that prevent later pain:
1. **Strata are difficulty axes, not topics.** Each stratum should predictably separate vendors (JS-rendered vs static; fresh vs old; ambiguous vs exact).
2. **Every metric must have a `-` semantics decision** — "no coverage" is never rendered as 0.
3. **`cost_per_correct` is mandatory** on every primitive. If you can't compute billed cost, you can't publish the metric agents care about most.

**Exit artifact:** the YAML, reviewed by one other person, merged.

---

## Stage 3 — Build the golden dataset (3–10 days · FDE designs, INT executes)

### 3a. Construction
- **Registry-sourced** (KYB, firmographics): write/extend the ingester; cohort assembled programmatically; human spot-check 5% of rows.
- **Curated** (URL sets, query sets): FDE writes the candidate-pool generator + auto-probing (stratum assignment); interns do the human verification pass at a budgeted ~2 min/row. 300 rows ≈ 10 intern-hours. Two-person verification on holdout rows.
- **Planted** (freshness): follow `golden/planted_pages/PROTOCOL.md` — generate, deploy across the 24-cell matrix, log authoritative T0 timestamps. **Deploy planted assets before anything else in this stage; the lag clock starts at deploy.**

### 3b. Quality gates
```
[ ] Every row has all golden fields populated + verified_at timestamp
[ ] 70/30 split is stratified (each stratum split proportionally)
[ ] Holdout file lives in the private repo only
[ ] Drift checks scheduled (weekly page-hash delta -> re-verification queue)
[ ] Rotation plan recorded: which 25% rotates next quarter
```

**Exit criteria:** `golden/<primitive>/` validates against the row schema; holdout count ≥25%; a dry-run of the scorer on 10 rows with a mocked perfect vendor returns fidelity 1.0 (catches schema/scorer mismatches before real spend).

---

## Stage 4 — Vendor adapters (1–2 days each · INT, parallelized)

The contract is `adapters/base.py`; the merge gate is `conformance_test.py`. Per adapter:

```
[ ] ToS status == cleared (re-check; it may have changed)
[ ] Endpoints verified against the vendor's CURRENT docs (this market ships
    breaking changes monthly — never trust memory or old examples)
[ ] All declared capabilities implemented; undeclared ones raise
[ ] Cost table filled from the archived pricing page (Stage 1 PDF)
[ ] Error mapping: 401/402/403 -> blocked; timeouts -> timeout; else fetch_failed
[ ] raw response persisted on every call (audit trail)
[ ] Conformance suite green; one --live call per capability recorded as fixture
```

FDE reviews every adapter PR. Adapters never normalize *meaning* — only transport. If you're tempted to "fix" a vendor's weird output in the adapter, that's a scoring rule, and it goes in `scoring/` where it's public and applied uniformly.

---

## Stage 5 — Scoring & dry run (1–2 days · FDE)

- Extend `scoring/engine.py` only with deterministic functions; every scoring rule gets a docstring that will be published verbatim on the methodology page.
- If a judged metric is unavoidable (<30% of items): pin model + version + prompt in the repo, score twice with two models, publish inter-judge agreement, human-audit 10%.
- **Dry run:** full pipeline on the public split only, 2 vendors, smallest viable cohort slice. Reconcile computed `cost_usd` against the vendors' actual billing dashboards — fix discrepancies now, not after a full run.

**Exit criteria:** dry-run snapshot builds; per-vendor aggregates look sane; spend reconciles within 10%.

---

## Stage 6 — Full snapshot run (1 day run + buffer · FDE)

```
[ ] Preflight passes (ToS gates, cost tables non-null, holdout >= 25%)
[ ] Holdout queries batched with decoys (dataset never leaves)
[ ] Rate limits respected per adapter (backoff from vendor headers)
[ ] Raw responses archived: public split -> repo artifact; holdout -> private
[ ] Snapshot ID minted: <primitive>-<year>-q<N>; snapshot is immutable forever
[ ] overfit_gap computed (public vs holdout accuracy delta per vendor)
```

---

## Stage 7 — Vendor review window (10 business days · F)

Before anything is public:
1. Email each vendor their own row + methodology link. Subject: "Your scores on wrodium-bench <primitive> — 10-day review window."
2. Accept *factual* corrections (wrong endpoint used, plan misidentified) — these trigger a re-run of affected cells, logged in an errata file.
3. Decline relitigation of methodology; offer the standing right-of-reply (published verbatim, length-capped, linked from their row).
4. No response after 10 days = publish as-is, noted.

This window is also the warmest possible sales touch: a vendor seeing a weak agent-readiness or freshness score, pre-publication, with a fix path — that's the Wrodium GEO conversation opening itself.

---

## Stage 8 — Publish all surfaces (1–2 days · FDE; design INT for the human view)

Ship simultaneously, never partially:

```
[ ] JSON API route serving the snapshot aggregates
[ ] llms.txt regenerated (full markdown rendering of the leaderboard)
[ ] OpenAPI 3.1 spec updated
[ ] MCP server: new task profile(s) wired into recommend(); query() exposes
    the primitive; /.well-known/mcp.json updated
[ ] Per-framework quickstarts: claude mcp add / Codex config.toml / Gemini
    settings.json blocks, copy-pasteable
[ ] Human leaderboard page (wrodium-brand skill applies) with: matrix,
    methodology, known limitations, exclusions + reasons, errata, vendor
    replies, license (CC-BY-4.0), independence disclosure
[ ] Methodology page = the scoring docstrings + golden design doc, verbatim
```

**Launch test (hard gate): a fresh Claude Code session, given only the bench homepage URL, must be able to discover the MCP server, call `recommend()`, and cite the snapshot ID — unaided.** If our own benchmark fails its own agent-readiness bar, it doesn't ship.

---

## Stage 9 — Telemetry & maintenance (ongoing · FDE 2–4 hrs/wk)

- MCP call logs reviewed weekly: which tasks/regions/budgets are agents asking about → next primitive prioritization input.
- ClawdBot/OpenClaw citation monitoring: track when ChatGPT/Claude/Gemini/Perplexity answers start citing the bench for "best X API" prompts.
- UA splits on llms.txt + JSON API (GPTBot/ClaudeBot/Gemini vs human).
- Drift checks auto-file re-verification tickets; dead golden rows replaced within 7 days from the same stratum.
- Quarterly: 25% cohort rotation, framework/judge version re-pin, harness re-run, snapshot re-mint. Lag crawlers (PPP, registry deltas) run continuously regardless — they are the moat and must never pause.

---

## Timeline & budget reference (per new benchmark)

| Stage | Calendar | Labor | Cash |
|---|---|---|---|
| 0–1 Qualify + legal | wk 1 | F: 1–2d, FDE: ½d | $0 |
| 2–3 Spec + golden | wk 1–2 | FDE: 2d, INT: 10–20h | <$200 compute |
| 4 Adapters | wk 2–3 (parallel) | INT: 1–2d × N vendors, FDE review | $0 |
| 5–6 Score + run | wk 3 | FDE: 2–3d | $200–1,500 vendor API spend |
| 7 Review window | wk 4–5 | F: light | $0 |
| 8 Publish | wk 5 | FDE: 2d, INT: design | $0 |
| **Total** | **~5 wks first time, ~3 wks once practiced** | | **<$2K/primitive** |

Benchmarks 2+ on a shared cohort (e.g. KYB after firmographics) skip most of Stage 3 and land in ~2 weeks.

---

## Anti-patterns (each has sunk a benchmark before)

- Writing adapters before the ToS gate. The gate exists because un-publishing is worse than not publishing.
- Letting a vendor's SDK do "helpful" cleanup inside the adapter — moves scoring logic somewhere private and non-uniform.
- Publishing accuracy without cost. Agents don't buy accuracy; they buy accuracy per dollar.
- Rendering missing coverage as 0. It's `-`, with semantics documented.
- Pausing the lag crawlers "temporarily." Gaps in the lag curves are permanent and visible.
- Launching the human page before the MCP surface. The agent is the customer; the human page is the press kit.
