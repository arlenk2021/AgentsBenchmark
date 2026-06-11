"""Stage 0 — qualify the primitive. The 5-row scorecard, as code.

A benchmark is worth building only if it scores >= 3 of 5. This module turns the
playbook's qualification table into a committable artifact and a pass/fail gate so
no one advances a primitive on vibes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..util import Report

CRITERIA = {
    "deterministic_truth": "Can a script/registry/page-we-control verify every answer? "
                           "(>30% LLM-judged => defer; needs insiders => reject)",
    "agents_are_buyers": "Do Claude Code / Codex / LangChain workflows select this vendor "
                         "category mid-task?",
    "freshness_scoreable": "Is there an objective event clock (filing date, publish time, "
                           "careers-page delta) to measure lag against?",
    "four_plus_vendors": ">= 4 vendors with public APIs (fewer is a matrix, not a market).",
    "wrodium_leverage": "Reuses an existing cohort/ingester/crawler, or feeds GEO lead-gen.",
}
# A hard reject regardless of total score: truth that needs insiders.
REJECT_FLAG = "truth_needs_insiders"


@dataclass
class Proposal:
    name: str
    rationale: str
    consumer_tasks: list[str]
    scores: dict[str, bool]            # criterion -> met?
    truth_needs_insiders: bool = False
    source_path: Path | None = None

    @property
    def total(self) -> int:
        return sum(1 for k in CRITERIA if self.scores.get(k))


def load_proposal(path: str | Path) -> Proposal:
    path = Path(path)
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Proposal(
        name=d.get("name", path.stem), rationale=d.get("rationale", ""),
        consumer_tasks=d.get("consumer_tasks", []), scores=d.get("scores", {}),
        truth_needs_insiders=d.get("truth_needs_insiders", False), source_path=path,
    )


def validate_proposal(p: Proposal) -> Report:
    r = Report(stage="Stage 0 — qualify the primitive")
    where = str(p.source_path or p.name)
    if not p.rationale.strip():
        r.error("proposal.no_rationale", "one-paragraph rationale is required", where)
    if not p.consumer_tasks:
        r.error("proposal.no_consumer_task",
                "name the consumer task(s) now — metrics get chosen to serve them", where)
    unknown = set(p.scores) - set(CRITERIA)
    for u in unknown:
        r.warn("proposal.unknown_criterion", f"'{u}' is not one of the 5 criteria", where)
    if p.truth_needs_insiders:
        r.error("proposal.rejected_insiders",
                "truth needs insiders (intent/traffic/revenue) — reject, do not build", where)
    if p.total < 3:
        r.error("proposal.below_threshold",
                f"scored {p.total}/5; a benchmark needs >= 3 of 5 to qualify", where)
    else:
        r.info("proposal.qualified", f"scored {p.total}/5 — qualifies", where)
    return r


PROPOSAL_TEMPLATE = """# Primitive proposal: {name}

name: {name}
consumer_tasks: []        # e.g. [page_extraction, fresh_content_monitor]

rationale: >
  One paragraph: what is scored, who the agent buyer is, why now.

# truth that needs insiders (intent / traffic / revenue) is an automatic reject:
truth_needs_insiders: false

# Stage 0 scorecard — mark each criterion met (true) or not (false). Need >= 3 of 5.
scores:
  deterministic_truth: false   # script/registry/page-we-control verifies every answer
  agents_are_buyers: false     # agent frameworks select this vendor category mid-task
  freshness_scoreable: false   # objective event clock exists to measure lag against
  four_plus_vendors: false     # >= 4 vendors with public APIs
  wrodium_leverage: false      # reuses a cohort/ingester/crawler or feeds GEO lead-gen
"""
