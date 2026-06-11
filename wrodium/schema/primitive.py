"""Primitive-spec model + validator (Stage 2, and the Stage 1 ToS verdict gate).

A *primitive* is one scoreable consumer task ("score vendors of X for agentic
consumers"). Its YAML is the single source of truth that every later stage reads:
adapters check `vendors[].tos_status`, the snapshot preflight checks cost tables
and the holdout ratio, the publisher renders `metrics` and `regions`.

The validator encodes, as hard ERRORs, the three rules the playbook says "prevent
later pain", plus the Stage-1 exit criterion that no vendor stays `pending_review`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..util import Report

# Stage-1 verdicts. `pending_review` is the only one the snapshot preflight rejects.
TOS_STATES = {"cleared", "static_rubric_only", "excluded", "pending_review"}
PUBLISHABLE_TOS = {"cleared", "static_rubric_only"}

# Terminal states a scored cell can land in (mirrors scoring.states.ResultState).
RESULT_STATES = {"correct", "incorrect", "no_coverage", "blocked", "timeout", "fetch_failed"}

REQUIRED_BLOCKS = (
    "task_shapes", "golden_sources", "cohort", "vendors", "scoring", "metrics", "regions",
)


@dataclass
class Vendor:
    key: str
    tos_status: str
    plan: str | None = None
    pricing_archived: str | None = None   # path to date-stamped PDF from Stage 1
    capabilities: list[str] = field(default_factory=list)
    cost_table: dict[str, float] = field(default_factory=dict)
    exclusion_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Stratum:
    key: str
    description: str = ""
    separates: str | None = None     # the difficulty axis this stratum discriminates
    weight: float | None = None


@dataclass
class Metric:
    key: str
    dash_semantics: str | None = None    # what "-" (no coverage) means for this metric
    direction: str = "higher_better"     # higher_better | lower_better
    unit: str | None = None
    description: str = ""


@dataclass
class Primitive:
    name: str
    consumer_tasks: list[str]
    task_shapes: list[Any]
    golden_sources: list[Any]
    cohort: dict[str, Any]
    vendors: list[Vendor]
    scoring: dict[str, Any]
    metrics: list[Metric]
    regions: list[str]
    raw: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None

    # ---- accessors used by later stages -------------------------------------
    @property
    def public_split(self) -> float:
        return float(self.cohort.get("split", {}).get("public", 0.7))

    @property
    def holdout_split(self) -> float:
        return float(self.cohort.get("split", {}).get("holdout", 0.3))

    @property
    def strata(self) -> list[Stratum]:
        out = []
        for s in self.cohort.get("strata", []):
            if isinstance(s, str):
                out.append(Stratum(key=s))
            else:
                out.append(Stratum(
                    key=s["key"], description=s.get("description", ""),
                    separates=s.get("separates"), weight=s.get("weight"),
                ))
        return out

    def vendor(self, key: str) -> Vendor | None:
        return next((v for v in self.vendors if v.key == key), None)

    @property
    def metric_keys(self) -> list[str]:
        return [m.key for m in self.metrics]


def load_primitive(path: str | Path) -> Primitive:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    vendors = [
        Vendor(
            key=v["key"], tos_status=v.get("tos_status", "pending_review"),
            plan=v.get("plan"), pricing_archived=v.get("pricing_archived"),
            capabilities=v.get("capabilities", []), cost_table=v.get("cost_table", {}),
            exclusion_reason=v.get("exclusion_reason"), raw=v,
        )
        for v in data.get("vendors", [])
    ]
    metrics = [
        Metric(
            key=m["key"], dash_semantics=m.get("dash_semantics"),
            direction=m.get("direction", "higher_better"),
            unit=m.get("unit"), description=m.get("description", ""),
        )
        for m in data.get("metrics", [])
    ]
    return Primitive(
        name=data.get("name", path.stem),
        consumer_tasks=data.get("consumer_tasks", []),
        task_shapes=data.get("task_shapes", []),
        golden_sources=data.get("golden_sources", []),
        cohort=data.get("cohort", {}),
        vendors=vendors,
        scoring=data.get("scoring", {}),
        metrics=metrics,
        regions=data.get("regions", []),
        raw=data, source_path=path,
    )


def validate_primitive(p: Primitive) -> Report:
    r = Report(stage="Stage 2 — primitive spec")
    where = str(p.source_path or p.name)

    # Required blocks present and non-empty.
    for block in REQUIRED_BLOCKS:
        val = p.raw.get(block)
        if not val:
            r.error("spec.missing_block", f"required block '{block}' is missing or empty", where)

    # Stage 0 decision record: consumer task(s) named before metrics.
    if not p.consumer_tasks:
        r.error("spec.no_consumer_task",
                "name the consumer task(s) (Stage 0) — metrics serve the task, never the reverse", where)

    # ---- Rule 3: cost_per_correct is mandatory on every primitive. ----------
    if "cost_per_correct" not in p.metric_keys:
        r.error("metric.missing_cost_per_correct",
                "every primitive must publish cost_per_correct — agents buy accuracy per dollar", where)

    # ---- Rule 2: every metric must decide its '-' (no coverage) semantics. ---
    for m in p.metrics:
        if not m.dash_semantics:
            r.error("metric.missing_dash_semantics",
                    f"metric '{m.key}' has no dash_semantics — 'no coverage' must never render as 0", where)

    # ---- Rule 1: strata are difficulty axes, not topics. --------------------
    strata = p.strata
    if not strata:
        r.error("cohort.no_strata", "cohort defines no strata", where)
    for s in strata:
        if not s.separates:
            r.warn("stratum.no_separates",
                   f"stratum '{s.key}' declares no `separates` axis — confirm it discriminates vendors, "
                   "not just topics", where)

    # 70/30 split present and summing to 1.
    split = p.cohort.get("split", {})
    if not split:
        r.error("cohort.no_split", "cohort.split (public/holdout) is required", where)
    elif abs((p.public_split + p.holdout_split) - 1.0) > 1e-6:
        r.error("cohort.split_not_unit",
                f"cohort.split must sum to 1.0 (got {p.public_split}+{p.holdout_split})", where)
    elif p.holdout_split < 0.25:
        r.error("cohort.holdout_too_small",
                f"holdout split {p.holdout_split:.0%} < 25% required by the golden gate", where)

    if not p.cohort.get("size"):
        r.warn("cohort.no_size", "cohort.size not declared", where)

    # ---- Vendors: Stage 1 ToS gate + pinned plan + cost table. --------------
    if len(p.vendors) < 4:
        r.warn("vendors.thin_market",
               f"only {len(p.vendors)} vendors — fewer than 4 makes a matrix, not a market (Stage 0)", where)
    keys = [v.key for v in p.vendors]
    for dup in {k for k in keys if keys.count(k) > 1}:
        r.error("vendors.duplicate_key", f"duplicate vendor key '{dup}'", where)

    for v in p.vendors:
        vloc = f"{where}::vendor:{v.key}"
        if v.tos_status not in TOS_STATES:
            r.error("vendor.bad_tos_status",
                    f"tos_status '{v.tos_status}' not in {sorted(TOS_STATES)}", vloc)
        if v.tos_status == "pending_review":
            r.error("vendor.tos_pending",
                    "Stage 1 exit: no vendor may remain pending_review (snapshot preflight hard-fails)", vloc)
        if v.tos_status == "excluded" and not v.exclusion_reason:
            r.error("vendor.no_exclusion_reason",
                    "excluded vendors need a one-line public reason (the 'not surveyed' pattern)", vloc)
        if v.tos_status in PUBLISHABLE_TOS:
            if not v.plan:
                r.error("vendor.no_pinned_plan",
                        "pin the cheapest published plan that exposes the capability (Stage 1)", vloc)
            if not v.cost_table:
                r.error("vendor.no_cost_table",
                        "cost_table is empty — cannot compute billed cost / cost_per_correct", vloc)
            if not v.pricing_archived:
                r.warn("vendor.no_pricing_archive",
                       "no date-stamped pricing archive recorded (Stage 1 PDF)", vloc)

    # ---- Scoring block sanity. ----------------------------------------------
    sc = p.scoring
    if sc:
        if not sc.get("method"):
            r.error("scoring.no_method", "scoring.method is required", where)
        if not sc.get("match_rules"):
            r.warn("scoring.no_match_rules", "scoring.match_rules not declared", where)
        declared_states = set(sc.get("result_states", RESULT_STATES))
        bad = declared_states - RESULT_STATES
        if bad:
            r.error("scoring.unknown_result_state",
                    f"unknown result_states {sorted(bad)} (allowed: {sorted(RESULT_STATES)})", where)

    # Judged-metric guardrail (Stage 5).
    if sc.get("method") == "judged" and not sc.get("judge"):
        r.error("scoring.judge_unpinned",
                "judged scoring must pin model+version+prompt and publish inter-judge agreement", where)

    return r
