"""Statute registry — the single source of truth for every legal fact papertrail asserts.

Every deadline, damage figure, and letter cite resolves to an entry here. This is the
anti-DoNotPay design choice made structural: the product never states a rule without a
verifiable citation attached, and the FTC's overclaiming failure mode is impossible
because nothing reaches the user unsourced.

Each `Citation` carries the controlling text we relied on, a public URL to verify it,
and `verified_on` — the date a human last checked the source still says this. Law
changes; an entry whose `verified_on` is stale is a re-verification ticket, exactly
like a drifted golden row in wrodium-bench.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    key: str
    title: str
    summary: str          # the rule, in one sentence, in plain English
    text: str             # the controlling statutory language we relied on
    url: str              # public, verifiable source
    verified_on: str      # ISO date a human last confirmed the source

    def render(self) -> str:
        return f"{self.title} — {self.summary} [verified {self.verified_on}]\n  {self.url}"


# ---------------------------------------------------------------------------
# California residential tenancy. Verified 2026-06-11 against the cited sources.
# ---------------------------------------------------------------------------
CITATIONS: dict[str, Citation] = {
    "ccp_1161": Citation(
        key="ccp_1161",
        title="Cal. Code Civ. Proc. § 1161(2)",
        summary="A 3-day notice to pay rent or quit counts 3 days EXCLUDING Saturdays, "
                "Sundays, and judicial holidays, starting the day after service.",
        text="Within three days, excluding Saturdays and Sundays and other judicial "
             "holidays, after the service of the notice, the tenant may perform the "
             "conditions or covenants of the lease ... or pay the stipulated rent.",
        url="https://codes.findlaw.com/ca/code-of-civil-procedure/ccp-sect-1161/",
        verified_on="2026-06-11",
    ),
    "ccp_1167": Citation(
        key="ccp_1167",
        title="Cal. Code Civ. Proc. § 1167 (as amended by AB 2347)",
        summary="A tenant served with an unlawful-detainer summons has 10 COURT days to "
                "file a response (doubled from 5 by AB 2347, effective Jan 1, 2025).",
        text="The defendant ... shall appear and answer ... within 10 days after the "
             "service of the summons ... computed by excluding ... weekends and "
             "judicial holidays (court days).",
        url="https://zakfisherlaw.com/10-court-day-answer-deadline-california-eviction/",
        verified_on="2026-06-11",
    ),
    "ab_2347": Citation(
        key="ab_2347",
        title="AB 2347 (Kalra, 2024)",
        summary="Signed Sept 24, 2024; effective Jan 1, 2025. Doubled the UD answer "
                "deadline from 5 to 10 court days and reformed demurrer timing.",
        text="This bill would extend the time for a defendant to respond to a complaint "
             "in an unlawful detainer action from 5 days to 10 days.",
        url="https://sjud.senate.ca.gov/system/files/2024-07/ab-2347-kalra-sjud-analysis_3.pdf",
        verified_on="2026-06-11",
    ),
    "civ_1946_1": Citation(
        key="civ_1946_1",
        title="Cal. Civ. Code § 1946.1",
        summary="No-fault termination needs 30 calendar days' notice if the tenant has "
                "lived there < 1 year, or 60 calendar days if >= 1 year.",
        text="An owner ... shall give notice at least 60 days prior to the proposed date "
             "of termination [if the tenant has resided in the dwelling for one year or "
             "more] ... [or] at least 30 days ... [if less than one year].",
        url="https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1946.1.",
        verified_on="2026-06-11",
    ),
    "civ_1950_5": Citation(
        key="civ_1950_5",
        title="Cal. Civ. Code § 1950.5(g)",
        summary="A landlord must return the deposit and an itemized statement within 21 "
                "CALENDAR days after the tenant vacates.",
        text="No later than 21 calendar days after the tenant has vacated the premises ... "
             "the landlord shall furnish the tenant ... a copy of an itemized statement "
             "indicating the basis for, and the amount of, any security received and the "
             "disposition of the security, and shall return any remaining portion.",
        url="https://codes.findlaw.com/ca/civil-code/civ-sect-1950-5/",
        verified_on="2026-06-11",
    ),
    "civ_1950_5_l": Citation(
        key="civ_1950_5_l",
        title="Cal. Civ. Code § 1950.5(l)",
        summary="A landlord who retains a deposit in bad faith may be liable for the "
                "deposit PLUS up to twice its amount in statutory damages.",
        text="The bad faith claim or retention by a landlord ... of the security or any "
             "portion thereof in violation of this section ... may subject the landlord "
             "... to statutory damages of up to twice the amount of the security, in "
             "addition to actual damages.",
        url="https://codes.findlaw.com/ca/civil-code/civ-sect-1950-5/",
        verified_on="2026-06-11",
    ),
    "ab_12": Citation(
        key="ab_12",
        title="AB 12 (2023), codified at Civ. Code § 1950.5(c)",
        summary="Since July 1, 2024, a deposit may not exceed one month's rent; a small "
                "landlord (natural person/LLC, <=2 properties, <=4 units) may charge up "
                "to two months', but never more than one month for a service member.",
        text="A landlord shall not demand or receive security ... in an amount or value "
             "in excess of an amount equal to one month's rent ... [small-landlord "
             "exception: up to two months' rent].",
        url="https://www.bhfs.com/insight/california-security-deposit-limits-effective-july-1-2024/",
        verified_on="2026-06-11",
    ),
    "ab_2801": Citation(
        key="ab_2801",
        title="AB 2801 (2024), amending Civ. Code § 1950.5",
        summary="Phases in photo-documentation duties; as of April 1, 2025 landlords must "
                "take move-out photos, and deductions must be supported by such evidence.",
        text="The landlord shall take photographs of the unit ... within a reasonable "
             "time after the ... termination of the tenancy [and] include copies with "
             "the itemized statement.",
        url="https://astanehelaw.com/2025/11/12/all-about-california-civil-code-%C2%A7-1950-5-the-california-security-deposit-law-2025-update/",
        verified_on="2026-06-11",
    ),
    "ccp_116_221": Citation(
        key="ccp_116_221",
        title="Cal. Code Civ. Proc. § 116.221",
        summary="Since Jan 1, 2024, a natural person may sue for up to $12,500 in small "
                "claims; entities are capped at $6,250.",
        text="The small claims court has jurisdiction in an action brought by a natural "
             "person if the amount of the demand does not exceed twelve thousand five "
             "hundred dollars ($12,500).",
        url="https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=116.221",
        verified_on="2026-06-11",
    ),
    "civ_1942_5": Citation(
        key="civ_1942_5",
        title="Cal. Civ. Code § 1942.5",
        summary="Retaliatory eviction is barred: a landlord may not evict or raise rent "
                "in retaliation for a tenant's lawful exercise of rights (e.g. a repair "
                "complaint) within 180 days.",
        text="[I]f the lessor retaliates against the lessee ... within 180 days [of the "
             "tenant's exercise of rights], the lessor may not recover possession ... in "
             "any action or proceeding.",
        url="https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1942.5.",
        verified_on="2026-06-11",
    ),
}


def cite(key: str) -> Citation:
    try:
        return CITATIONS[key]
    except KeyError:
        raise KeyError(f"no citation registered for '{key}' — every legal assertion must be sourced")


def stale_citations(as_of: str, *, max_age_days: int = 120) -> list[Citation]:
    """Citations not human-verified within max_age_days of `as_of` (ISO date).
    Drives the re-verification queue — the legal analogue of wrodium-bench drift checks."""
    import datetime as _dt
    cutoff = _dt.date.fromisoformat(as_of) - _dt.timedelta(days=max_age_days)
    return [c for c in CITATIONS.values() if _dt.date.fromisoformat(c.verified_on) < cutoff]
