"""Golden-row schema + dataset validator (Stage 3).

A golden row is one cohort item with its verified truth. The dataset is split
public/holdout; the holdout file lives only in the private repo. The validator
enforces the Stage-3 quality gates: every field populated + verified, stratified
split, holdout >= 25%.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..util import Report, read_jsonl
from .primitive import Primitive

SPLITS = {"public", "holdout"}


@dataclass
class GoldenRow:
    id: str
    stratum: str
    region: str
    split: str
    golden: dict[str, Any]          # the verified truth fields the scorer compares against
    verified_at: str | None = None  # ISO timestamp; two-person on holdout
    source_url: str | None = None
    page_hash: str | None = None    # for weekly drift checks
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "GoldenRow":
        return cls(
            id=str(d.get("id", "")), stratum=d.get("stratum", ""),
            region=d.get("region", ""), split=d.get("split", ""),
            golden=d.get("golden", {}), verified_at=d.get("verified_at"),
            source_url=d.get("source_url"), page_hash=d.get("page_hash"), raw=d,
        )


def load_golden(path: str | Path) -> list[GoldenRow]:
    return [GoldenRow.from_dict(d) for d in read_jsonl(Path(path))]


def validate_golden(rows: list[GoldenRow], primitive: Primitive, *, where: str = "golden") -> Report:
    r = Report(stage="Stage 3 — golden dataset")
    if not rows:
        r.error("golden.empty", "no golden rows loaded", where)
        return r

    valid_strata = {s.key for s in primitive.strata}
    valid_regions = set(primitive.regions)
    golden_fields = set(primitive.scoring.get("golden_fields", []))
    ids: list[str] = []

    for row in rows:
        rloc = f"{where}::{row.id or '?'}"
        ids.append(row.id)
        if not row.id:
            r.error("row.no_id", "row missing id", rloc)
        if row.split not in SPLITS:
            r.error("row.bad_split", f"split '{row.split}' not in {sorted(SPLITS)}", rloc)
        if valid_strata and row.stratum not in valid_strata:
            r.error("row.bad_stratum", f"stratum '{row.stratum}' not declared in primitive", rloc)
        if valid_regions and row.region not in valid_regions:
            r.warn("row.bad_region", f"region '{row.region}' not declared in primitive", rloc)
        # Every golden field populated + verified.
        if not row.verified_at:
            r.error("row.unverified", "row has no verified_at timestamp", rloc)
        missing = [f for f in golden_fields if f not in row.golden or row.golden.get(f) in (None, "")]
        if missing:
            r.error("row.missing_golden_fields",
                    f"golden fields not populated: {missing}", rloc)

    for dup in {i for i in ids if ids.count(i) > 1}:
        r.error("golden.duplicate_id", f"duplicate row id '{dup}'", where)

    # Holdout >= 25%.
    n = len(rows)
    holdout = [x for x in rows if x.split == "holdout"]
    holdout_frac = len(holdout) / n if n else 0
    if holdout_frac < 0.25:
        r.error("golden.holdout_too_small",
                f"holdout is {holdout_frac:.0%} of {n} rows (< 25% required)", where)

    # Stratified split: each stratum split proportionally to the target.
    target_holdout = primitive.holdout_split
    by_stratum: dict[str, list[GoldenRow]] = {}
    for row in rows:
        by_stratum.setdefault(row.stratum, []).append(row)
    for stratum, group in by_stratum.items():
        gh = sum(1 for x in group if x.split == "holdout") / len(group)
        if abs(gh - target_holdout) > 0.15:
            r.warn("golden.stratum_split_skew",
                   f"stratum '{stratum}' holdout {gh:.0%} vs target {target_holdout:.0%} "
                   "(split should be stratified proportionally)", where)

    r.info("golden.summary", f"{n} rows, {len(by_stratum)} strata, holdout {holdout_frac:.0%}", where)
    return r
