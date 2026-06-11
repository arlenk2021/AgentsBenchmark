"""The "can I keep this fish?" decision engine.

Takes a species, a measured size, a count already kept, and an optional region, and
returns a clear KEEP / RELEASE / CLOSED verdict with the reason and the citation. The
design bias is toward RELEASE under any uncertainty — the cost of a wrong "keep" is a
fine ($100-$1,000 first offense; far more for abalone/trophy), so an ambiguous case
never returns "keep".
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .regdb import RegDB, Species, Rule


class Verdict(str, Enum):
    KEEP = "keep"
    RELEASE = "release"
    CLOSED = "closed"          # season/fishery closed — do not take at all
    UNKNOWN = "unknown"        # not in DB — refuse to guess


CLOSED_SEASONS = {"closed", "frequently_closed"}


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    species_key: str | None
    rule: Rule | None
    citation: str | None
    confidence: str            # "high" | "verify" (stale rule / fallback region)
    warnings: tuple[str, ...] = ()

    def render(self) -> str:
        head = {
            Verdict.KEEP: "✅ KEEP — appears legal",
            Verdict.RELEASE: "↩️  RELEASE — not legal to keep",
            Verdict.CLOSED: "⛔ CLOSED — do not take",
            Verdict.UNKNOWN: "❓ UNKNOWN — not in the verified database",
        }[self.verdict]
        lines = [head, f"   {self.reason}"]
        if self.citation:
            lines.append(f"   Authority: {self.citation}")
        if self.confidence == "verify":
            lines.append("   ⚠️  Confidence: VERIFY against current CDFW regs before relying on this.")
        for w in self.warnings:
            lines.append(f"   ⚠️  {w}")
        return "\n".join(lines)


def can_i_keep(db: RegDB, *, species: str, size_in: float | None = None,
               region: str | None = None, already_kept: int = 0,
               as_of: str | None = None) -> Decision:
    sp: Species | None = db.find(species)
    if sp is None:
        return Decision(Verdict.UNKNOWN,
                        f"'{species}' is not in the verified database — do not guess; check CDFW.",
                        None, None, None, "verify")

    rule = sp.rule_for(region)
    if rule is None:
        return Decision(Verdict.UNKNOWN, f"No rule found for {sp.key}.", sp.key, None, None, "verify")

    warnings: list[str] = []
    confidence = "high"
    # Region fallback → demote confidence.
    if region and rule.region != region and "statewide" not in rule.region and "default" not in rule.region:
        confidence = "verify"
        warnings.append(f"Used rule for '{rule.region}', not your stated region '{region}'.")
    # Stale verification → demote confidence (annual reg churn).
    if as_of and rule.verified_on:
        stale = db.stale_rules(as_of)
        if any(k == sp.key and r.region == rule.region for k, r in stale):
            confidence = "verify"
            warnings.append(f"This rule was last verified {rule.verified_on} — fishing regs change yearly.")
    if rule.season_note:
        warnings.append(rule.season_note)

    # 1. Closed season/fishery dominates everything.
    if rule.season in CLOSED_SEASONS:
        return Decision(Verdict.CLOSED,
                        f"The {sp.key} season is '{rule.season}'. Do not take.",
                        sp.key, rule, rule.citation, "verify" if rule.season == "frequently_closed" else "high",
                        tuple(warnings))
    if rule.daily_bag == 0:
        return Decision(Verdict.CLOSED, f"Daily bag limit for {sp.key} is 0 — none may be kept.",
                        sp.key, rule, rule.citation, confidence, tuple(warnings))

    # 2. Bag limit already reached.
    if rule.daily_bag is not None and already_kept >= rule.daily_bag:
        return Decision(Verdict.RELEASE,
                        f"You've reached the daily bag limit of {rule.daily_bag} for {sp.key}.",
                        sp.key, rule, rule.citation, confidence, tuple(warnings))

    # 3. Size checks. Missing measurement when a size rule exists → refuse to say keep.
    if (rule.min_size_in is not None or rule.max_size_in is not None) and size_in is None:
        warnings.append("Measure the fish — a size limit applies and no length was given.")
        return Decision(Verdict.RELEASE,
                        f"{sp.key} has a size limit but no measurement was provided; do not keep until measured.",
                        sp.key, rule, rule.citation, "verify", tuple(warnings))
    if rule.min_size_in is not None and size_in is not None and size_in < rule.min_size_in:
        return Decision(Verdict.RELEASE,
                        f"{size_in}\" is under the {rule.min_size_in}\" minimum for {sp.key}.",
                        sp.key, rule, rule.citation, confidence, tuple(warnings))
    if rule.max_size_in is not None and size_in is not None and size_in > rule.max_size_in:
        return Decision(Verdict.RELEASE,
                        f"{size_in}\" exceeds the {rule.max_size_in}\" maximum for {sp.key}.",
                        sp.key, rule, rule.citation, confidence, tuple(warnings))

    # 4. Passed all gates.
    size_txt = f"at {size_in}\" " if size_in is not None else ""
    bag_txt = (f"; you may keep {rule.daily_bag - already_kept} more (limit {rule.daily_bag})"
               if rule.daily_bag is not None else "")
    return Decision(Verdict.KEEP,
                    f"{sp.key} {size_txt}meets size and season rules{bag_txt}.",
                    sp.key, rule, rule.citation, confidence, tuple(warnings))
