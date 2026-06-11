"""Notice-type classifier.

Turns the document a tenant was handed into a known notice type so the right deadline
function and explanation fire. Deliberately rule-based and transparent — it returns the
signals it matched on, never a black-box label, so a user (or a court) can see why.

A confident classification routes to a deadline; a low-confidence one routes to "talk
to a human / legal aid", because misclassifying a 3-day pay-or-quit as a 30-day notice
would compute a catastrophically wrong deadline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    notice_type: str          # pay_or_quit | cure_or_quit | unconditional_quit |
                              # termination_30 | termination_60 | unlawful_detainer | unknown
    deadline_fn: str | None   # which DeadlineEngine method applies, if any
    confidence: float
    signals: tuple[str, ...]  # the phrases matched, for transparency
    guidance: str


# (regex, notice_type, deadline_fn, weight) — order independent; scores accumulate.
_RULES: list[tuple[str, str, str | None, float]] = [
    (r"\b3[- ]?day\b|\bthree[- ]?day\b", "pay_or_quit", "pay_or_quit", 0.4),
    (r"pay rent or quit|pay or quit|nonpayment of rent|past due rent", "pay_or_quit", "pay_or_quit", 0.5),
    (r"perform covenant|cure or quit|correct the violation|lease violation", "cure_or_quit", "pay_or_quit", 0.4),
    (r"unconditional|quit the premises\b(?!.*pay)", "unconditional_quit", None, 0.3),
    (r"\b30[- ]?day\b|\bthirty[- ]?day\b", "termination_30", "termination_notice", 0.4),
    (r"\b60[- ]?day\b|\bsixty[- ]?day\b", "termination_60", "termination_notice", 0.4),
    (r"terminat\w+ of tenancy|notice to vacate|end your tenancy", "termination_30", "termination_notice", 0.3),
    (r"summons|unlawful detainer|complaint .*possession|UD[- ]?\d", "unlawful_detainer", "ud_answer", 0.6),
    (r"you have .* to (respond|answer)|file .* response", "unlawful_detainer", "ud_answer", 0.3),
]


def classify(text: str) -> Classification:
    t = text.lower()
    scores: dict[str, float] = {}
    fns: dict[str, str | None] = {}
    signals: list[str] = []
    for pattern, ntype, fn, weight in _RULES:
        if re.search(pattern, t):
            scores[ntype] = scores.get(ntype, 0.0) + weight
            fns[ntype] = fn
            signals.append(pattern)

    if not scores:
        return Classification("unknown", None, 0.0, (),
                              "Could not identify this notice. Take it to legal aid or a tenant "
                              "clinic — do not rely on a guessed deadline.")

    best = max(scores, key=scores.get)
    conf = min(scores[best], 1.0)

    # An unlawful-detainer summons is time-critical and overrides softer matches.
    if "unlawful_detainer" in scores and scores["unlawful_detainer"] >= 0.6:
        best, conf = "unlawful_detainer", min(scores["unlawful_detainer"], 1.0)

    guidance = {
        "pay_or_quit": "This is a pay/cure-or-quit notice. You have a short COURT-day window to "
                       "pay or fix the issue before the landlord can sue. Compute the exact date.",
        "cure_or_quit": "This is a cure-or-quit notice for a lease violation. Same short court-day "
                        "window applies.",
        "unconditional_quit": "This demands you leave with no chance to cure. These are restricted "
                              "in CA — confirm the stated grounds are lawful.",
        "termination_30": "This is a no-fault termination notice. If you've lived there a year or "
                          "more, 30 days is too short — it must be 60.",
        "termination_60": "This is a 60-day no-fault termination notice (1+ year tenancy).",
        "unlawful_detainer": "This is an eviction LAWSUIT. You must file a written response within "
                             "10 COURT days or risk losing by default. This is the critical deadline.",
    }.get(best, "Identified, but confirm with legal aid.")

    if conf < 0.4:
        guidance = "Low-confidence match — verify with a human before acting. " + guidance

    return Classification(best, fns.get(best), round(conf, 2), tuple(signals), guidance)
