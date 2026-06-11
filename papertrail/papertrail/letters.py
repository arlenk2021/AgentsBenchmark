"""Letter generator — UPL-safe by construction.

The unauthorized-practice-of-law (UPL) risk is the real existential threat to a solo
CA build, bigger than the FTC angle. Cal. Bus. & Prof. Code § 6125-6126 bars practicing
law without a license; "preparing legal documents" can cross into Legal Document
Assistant territory (§ 6400). So this module is built to stay on the safe side of that
line, structurally:

  * It produces INFORMATION and a FILL-IN-THE-BLANKS letter in the user's own voice —
    it never signs, never files, never says "we will represent you."
  * Every legal statement carries a statute citation the user can verify (anti-DoNotPay).
  * It states scope and disclaims legal advice on every output.
  * It computes nothing it can't source; deadlines come from the verified engine.

The product's pitch is "organize your facts into a sourced, court-ready letter you send
yourself," not "robot lawyer." That contrast is the credibility story.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from .citations import cite
from .deadlines import Deadline

DISCLAIMER = (
    "This letter was assembled by papertrail from information you provided and from the "
    "California statutes cited below. papertrail is not a law firm and does not provide "
    "legal advice or representation. Verify the citations, confirm the facts, and consider "
    "consulting a tenant attorney or legal-aid clinic before you send or file anything. "
    "You are the author and sender of this letter."
)


@dataclass(frozen=True)
class Letter:
    title: str
    body: str
    citations_used: tuple[str, ...]

    def render(self) -> str:
        cites = "\n".join(f"  - {cite(k).title}: {cite(k).summary}\n    {cite(k).url}"
                          for k in self.citations_used)
        return (f"{self.body}\n\n"
                f"---\nLegal authorities referenced:\n{cites}\n\n"
                f"---\n{DISCLAIMER}")


def _blank(label: str) -> str:
    return f"[{label}]"


def deposit_demand(*, tenant: str | None, landlord: str | None, address: str | None,
                   deposit_amount: float, vacated: _dt.date, deadline: Deadline,
                   bad_faith: bool = False, today: _dt.date | None = None) -> Letter:
    """A § 1950.5 demand for an unreturned deposit, in the tenant's voice.

    If the 21-day deadline has passed, states the forfeiture rule and (when warranted)
    the up-to-2x bad-faith exposure — as information with citations, not as a threat or
    a legal conclusion the product asserts on the user's behalf."""
    today = today or _dt.date.today()
    cites = ["civ_1950_5"]
    overdue = deadline.last_day is not None and today > deadline.last_day

    paras = [
        f"Date: {today:%B %d, %Y}",
        f"From: {tenant or _blank('your name')}",
        f"To: {landlord or _blank('landlord name')}",
        f"Re: Return of security deposit for {address or _blank('rental address')}",
        "",
        f"I vacated the above unit on {vacated:%B %d, %Y}. I paid a security deposit of "
        f"${deposit_amount:,.2f}.",
        "",
        f"Under California Civil Code § 1950.5(g), a landlord must return the deposit and "
        f"provide an itemized statement within 21 calendar days after the tenant vacates — "
        f"here, by {deadline.last_day:%B %d, %Y}." if deadline.last_day else
        "Under California Civil Code § 1950.5(g), a landlord must return the deposit and "
        "an itemized statement within 21 calendar days after the tenant vacates.",
    ]
    if overdue:
        paras += [
            "",
            f"As of today, more than 21 days have passed and I have not received the deposit "
            f"or a compliant itemized statement. Under § 1950.5(f), the right to retain any "
            f"portion of the deposit has not been perfected, and I am requesting return of the "
            f"full ${deposit_amount:,.2f}.",
        ]
        if bad_faith:
            cites.append("civ_1950_5_l")
            paras += [
                "",
                "Civil Code § 1950.5(l) provides that bad-faith retention may subject a landlord "
                "to statutory damages of up to twice the amount of the deposit, in addition to "
                "actual damages. I would prefer to resolve this without a small-claims action.",
            ]
        cites.append("ccp_116_221")
        paras += [
            "",
            "If I do not receive the deposit within 14 days, I intend to pursue my remedies in "
            "small claims court (which has jurisdiction up to $12,500 for an individual under "
            "Code of Civil Procedure § 116.221).",
        ]
    else:
        paras += [
            "",
            f"I am writing to confirm the deposit's return on time. Please send it to the address "
            f"below by {deadline.last_day:%B %d, %Y}." if deadline.last_day else
            "Please confirm the deposit will be returned within the statutory 21 days.",
        ]
    paras += ["", "Sincerely,", tenant or _blank("your signature")]
    return Letter("Security deposit demand (Cal. Civ. Code § 1950.5)", "\n".join(paras), tuple(cites))


def deadline_summary(deadline: Deadline) -> Letter:
    """Not a letter to send — a sourced, plain-English summary of a computed deadline
    for the user's own records. Keeps the 'information, not advice' framing explicit."""
    body_lines = [
        f"Your computed deadline: {deadline.kind}",
        "",
        deadline.explanation,
    ]
    if deadline.last_day:
        body_lines.append(f"\nLast day to act: {deadline.last_day:%A, %B %d, %Y} "
                          f"({deadline.mode} days).")
    else:
        body_lines.append("\nThis situation needs human review before a date can be relied on.")
    if deadline.days_excluded:
        body_lines.append("\nDays that did not count toward the deadline:")
        body_lines += [f"  - {d}" for d in deadline.days_excluded]
    for note in deadline.notes:
        body_lines.append(f"\nNote: {note}")
    return Letter(f"Deadline summary — {deadline.kind}", "\n".join(body_lines),
                  (deadline.citation.key,))
