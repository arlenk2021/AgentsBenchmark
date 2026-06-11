# papertrail / depositback — market & legal grounding

Companion to the build. Every legal figure below was re-verified against primary or
authoritative sources on **2026-06-11**, and several **corrected** the original product
analysis. Corrections are flagged ⚠️ — they matter because the deadline engine encodes
them, and a wrong one loses a user their home.

## Verified legal facts (and corrections to the original analysis)

| Fact | Verified value | Source | Note |
|---|---|---|---|
| UD answer deadline (AB 2347) | **10 COURT days**, eff. Jan 1, 2025 (signed Sep 24, 2024) | [SJUD analysis](https://sjud.senate.ca.gov/system/files/2024-07/ab-2347-kalra-sjud-analysis_3.pdf), [zakfisherlaw](https://zakfisherlaw.com/10-court-day-answer-deadline-california-eviction/) | ⚠️ The analysis said "business days." It's **court days** (excl. weekends + judicial holidays) — a materially different, usually *longer* count. |
| 3-day pay-or-quit count | 3 days **excluding** Sat/Sun + judicial holidays | [CCP §1161, FindLaw](https://codes.findlaw.com/ca/code-of-civil-procedure/ccp-sect-1161/) | ⚠️ Often longer than 3 calendar days; the engine computes the exact court-day date. |
| No-fault termination notice | 30 **calendar** days (<1 yr occupancy) / 60 (≥1 yr) | [Civ. Code §1946.1](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1946.1.) | ⚠️ These are calendar, not court, days — a different counting mode from the 3/10-day notices. The engine keeps the two modes separate. |
| Deposit return clock | **21 calendar days** after vacating | [Civ. Code §1950.5(g)](https://codes.findlaw.com/ca/civil-code/civ-sect-1950-5/) | Miss it → right to withhold not perfected (§1950.5(f)). |
| Bad-faith deposit damages | Up to **2× the deposit** + actual damages | [Civ. Code §1950.5(l)](https://codes.findlaw.com/ca/civil-code/civ-sect-1950-5/) | A $2,500 deposit → up to $7,500 exposure. |
| Deposit cap (AB 12) | **1 month's rent**; small landlord 2 months; service member always 1 | [Brownstein](https://www.bhfs.com/insight/california-security-deposit-limits-effective-july-1-2024/) | Eff. July 1, 2024. Small landlord = natural person/LLC, ≤2 properties, ≤4 units. |
| Move-out photo duty (AB 2801) | Landlord must take move-out photos; deductions need evidence | [Astanehe Law](https://astanehelaw.com/2025/11/12/all-about-california-civil-code-%C2%A7-1950-5-the-california-security-deposit-law-2025-update/) | Phased in through 2025 (April 1, 2025 move-out photos). |
| Small-claims cap | **$12,500** individual / **$6,250** entities, eff. Jan 1, 2024 | [CCP §116.221](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=116.221) | ⚠️ The analysis cited only $12,500; the entity cap is half that — relevant if the landlord is an LLC suing the tenant. |

## Market sizing (as cited in the analysis, not independently re-pulled here)

- ~136,000 CA eviction filings FY2024 (PPIC); Alameda up ~50% vs. 2019.
- <5% of tenants have counsel vs. >80% of landlords; ~40% lose by default (researcher estimate, CalMatters).
- Avg US deposit ~$750 (Zillow 2024); ~26%+ renters report deposit denial; 41% report a move-out dispute.

These are reused from the prior research and should be re-verified before any public claim; they are **not** encoded in the engine, so a stale market number can't produce a wrong user deadline.

## The two failure modes the build is designed against

**1. Legal hallucination (the "why not ChatGPT" moat).** The benchmark in `bench/`
makes this empirical rather than rhetorical: on 11 verifiable CA deadline scenarios the
engine scores **100%** while a naive LLM-style baseline (calendar-day counting, no
holidays, guessing on ambiguous service) scores **36%** — i.e. **64% wrong**, squarely
inside the Stanford RegLab "Large Legal Fictions" 58–88% range. Run it:

```bash
python bench/run_benchmark.py        # prints both accuracies and the gate verdict
```

The gate is the product decision: **if the engine is not 100%, the deadline feature does
not ship** — only the (still-useful, lower-risk) evidence log and explainer do.

**2. Unauthorized practice of law (UPL) — the bigger existential risk for a solo build.**
Cal. Bus. & Prof. Code §§6125–6126 bar practicing law without a license; §6400 regulates
Legal Document Assistants. DoNotPay's FTC order (finalized Feb 11, 2025: $193,000 relief;
barred from claiming it "performs like a real lawyer" without evidence) is the *advertising*
cautionary tale; UPL is the *conduct* one. papertrail's design choices that keep it on the
safe side, structurally:

- Letters are generated in the **user's own voice**, for the user to send/file themselves
  — never signed, filed, or sent by papertrail (`letters.py`).
- Every legal statement carries a **statute citation** the user can verify
  (`citations.py`); nothing reaches the user unsourced.
- A **scope disclaimer** ("not a law firm, not legal advice") is appended to every letter.
- The engine **refuses** (returns `needs_review`) on ambiguous inputs — non-personal
  service, unknown occupancy length — rather than assert a possibly-wrong legal deadline.

## Product sequencing (what the build reflects)

1. **depositback is the front door.** Same engine/statute/user, but "how do I get my
   deposit back" is calm, high-volume, and trust-building, where "I'm being evicted" is
   low-volume and high-distress. `deposit.py` is therefore a first-class module, not a
   footnote.
2. **papertrail (eviction kit) is the flagship** the deposit funnel earns the right to
   sell — gated on the deadline benchmark.
3. Pricing target: $39–$49 one-time "case unlock" (matches DoNotPay's psychological price,
   avoids subscription resentment in a one-time crisis).
