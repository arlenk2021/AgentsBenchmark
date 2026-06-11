"""Deterministic scoring engine (Stage 5).

Every function here is pure and deterministic, and **its docstring is published
verbatim on the methodology page** — so write each one to be read by a vendor who
disagrees with their score. Add only deterministic functions here. A judged metric
is a last resort (Stage 5) and lives behind `judge.py`, never inlined.

The engine maps a `CallResult` + the golden truth to exactly one `ResultState`,
using the `match_rules` declared in the primitive YAML. Adapters never normalize
meaning; all normalization that affects scoring lives here, applied uniformly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from ..adapters.base import CallResult, CallState
from .states import ResultState

# --- match primitives: each returns True iff the candidate matches the golden ---


def _norm(s: Any) -> str:
    """Lowercase, collapse internal whitespace, strip — the canonical string
    normalization applied before every string comparison."""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def match_exact(candidate: Any, golden: Any) -> bool:
    """Byte-for-byte equality after type coercion to str. Use for IDs and codes
    where any deviation is wrong (CIK, NPI, ISO codes)."""
    return str(candidate) == str(golden)


def match_normalized_string(candidate: Any, golden: Any) -> bool:
    """Equality after case-folding and whitespace collapse. Use for names and
    short free-text where casing/spacing is not semantically meaningful."""
    return _norm(candidate) == _norm(golden)


def match_url(candidate: Any, golden: Any) -> bool:
    """URL equality ignoring scheme, leading 'www.', trailing slash, and case of
    the host. Query strings and paths are compared case-sensitively below the host."""
    def canon(u: str) -> str:
        u = str(u).strip()
        u = re.sub(r"^https?://", "", u, flags=re.I)
        u = re.sub(r"^www\.", "", u, flags=re.I)
        u = u.rstrip("/")
        host, _, rest = u.partition("/")
        return host.lower() + ("/" + rest if rest else "")
    return canon(candidate) == canon(golden)


def match_numeric_tolerance(candidate: Any, golden: Any, *, tol: float = 0.0) -> bool:
    """Numeric equality within an absolute tolerance `tol`. Non-numeric candidate
    is an automatic miss (it never raises)."""
    try:
        return abs(float(candidate) - float(golden)) <= tol
    except (TypeError, ValueError):
        return False


def match_set_overlap(candidate: Any, golden: Any, *, threshold: float = 1.0) -> bool:
    """Jaccard-style coverage: |cand ∩ gold| / |gold| >= threshold, over normalized
    string members. threshold=1.0 means the candidate must contain every golden
    member (recall-complete). Use for tag/category extraction."""
    gold = {_norm(x) for x in (golden or [])}
    cand = {_norm(x) for x in (candidate or [])}
    if not gold:
        return not cand
    return len(cand & gold) / len(gold) >= threshold


MATCHERS: dict[str, Callable[..., bool]] = {
    "exact": match_exact,
    "normalized_string": match_normalized_string,
    "url": match_url,
    "numeric_tolerance": match_numeric_tolerance,
    "set_overlap": match_set_overlap,
}


@dataclass
class CellScore:
    vendor: str
    row_id: str
    state: ResultState
    cost_usd: float
    latency_ms: float
    field_results: dict[str, bool]   # per-field match outcomes (audit/explanation)
    detail: str = ""


# --- mapping transport state -> result state -----------------------------------

_TRANSPORT = {
    CallState.BLOCKED: ResultState.BLOCKED,
    CallState.TIMEOUT: ResultState.TIMEOUT,
    CallState.FETCH_FAILED: ResultState.FETCH_FAILED,
}


def _matcher_for(field: str, rules: dict) -> tuple[Callable[..., bool], dict]:
    rule = rules.get(field, rules.get("_default", {"matcher": "normalized_string"}))
    if isinstance(rule, str):
        rule = {"matcher": rule}
    fn = MATCHERS.get(rule.get("matcher", "normalized_string"))
    if fn is None:
        raise ValueError(f"unknown matcher '{rule.get('matcher')}' for field '{field}'")
    kwargs = {k: v for k, v in rule.items() if k != "matcher"}
    return fn, kwargs


def score_cell(result: CallResult, golden: dict, *, scoring: dict, row_id: str = "") -> CellScore:
    """Score one (vendor, row) cell deterministically.

    A transport failure short-circuits to its terminal state. An OK call with an
    empty/missing payload is `no_coverage` (rendered '-', never 0). Otherwise the
    cell is `correct` iff every golden field matches under its declared rule; any
    miss makes it `incorrect`.
    """
    if result.state in _TRANSPORT:
        return CellScore(result.vendor, row_id, _TRANSPORT[result.state],
                         result.cost_usd, result.latency_ms, {}, result.error or "")

    golden_fields = list(scoring.get("golden_fields", golden.keys()))
    rules = scoring.get("match_rules", {})
    value = result.value or {}

    # No coverage: the vendor returned an OK call but nothing usable for this item.
    has_any = isinstance(value, dict) and any(
        value.get(f) not in (None, "", [], {}) for f in golden_fields
    )
    if not has_any:
        return CellScore(result.vendor, row_id, ResultState.NO_COVERAGE,
                         result.cost_usd, result.latency_ms, {}, "empty payload")

    field_results: dict[str, bool] = {}
    for f in golden_fields:
        fn, kwargs = _matcher_for(f, rules)
        field_results[f] = bool(fn(value.get(f), golden.get(f), **kwargs))

    state = ResultState.CORRECT if all(field_results.values()) else ResultState.INCORRECT
    misses = [f for f, ok in field_results.items() if not ok]
    return CellScore(result.vendor, row_id, state, result.cost_usd, result.latency_ms,
                     field_results, detail="" if not misses else f"missed: {misses}")
