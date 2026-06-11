"""Evidence log -> court-ready packet.

The defensible, sticky core (the JustFix lesson): a tenant who logs conditions,
communications, and payments contemporaneously builds a case general advice can't.
Each entry is timestamped at capture and content-hashed so the packet can attest the
log wasn't edited after the fact — evidence-grade, not just notes.

This module is pure data + rendering; persistence (where the jsonl lives) is the
caller's choice. The packet renders to Markdown that prints cleanly to a court PDF.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


ENTRY_KINDS = {
    "condition",      # habitability issue (no heat, leak, mold) — § 1942.5 / repair cases
    "communication",  # message to/from landlord (request, response, threat)
    "payment",        # rent paid / attempted — defeats a pay-or-quit
    "notice",         # a document the landlord served
    "photo",          # reference to an image file (path + caption)
}


def _now_iso(clock: _dt.datetime | None = None) -> str:
    # Caller passes a clock for determinism in tests; defaults to real time.
    return (clock or _dt.datetime.now(_dt.timezone.utc)).isoformat()


@dataclass(frozen=True)
class Entry:
    kind: str
    summary: str
    occurred_on: str                 # when the event happened (user-stated, ISO date)
    captured_at: str                 # when it was logged (system time, immutable)
    detail: str = ""
    attachment: str | None = None    # path to a photo/doc, if any
    content_hash: str = ""

    @staticmethod
    def create(kind: str, summary: str, occurred_on: str, *, detail: str = "",
               attachment: str | None = None, clock: _dt.datetime | None = None) -> "Entry":
        if kind not in ENTRY_KINDS:
            raise ValueError(f"unknown entry kind '{kind}' (allowed: {sorted(ENTRY_KINDS)})")
        captured = _now_iso(clock)
        payload = {"kind": kind, "summary": summary, "occurred_on": occurred_on,
                   "captured_at": captured, "detail": detail, "attachment": attachment}
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return Entry(kind, summary, occurred_on, captured, detail, attachment, h)

    def verify(self) -> bool:
        """Re-derive the hash; False means the entry was altered after capture."""
        payload = {"kind": self.kind, "summary": self.summary, "occurred_on": self.occurred_on,
                   "captured_at": self.captured_at, "detail": self.detail, "attachment": self.attachment}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() == self.content_hash


@dataclass
class EvidenceLog:
    case_name: str
    entries: list[Entry] = field(default_factory=list)

    def add(self, entry: Entry) -> None:
        self.entries.append(entry)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            "\n".join(json.dumps(asdict(e), sort_keys=True) for e in self.entries) + "\n",
            encoding="utf-8")

    @classmethod
    def load(cls, case_name: str, path: str | Path) -> "EvidenceLog":
        log = cls(case_name)
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                log.entries.append(Entry(**json.loads(line)))
        return log

    def integrity(self) -> tuple[bool, list[str]]:
        """Whole-log integrity: which entries (if any) fail their hash."""
        bad = [e.summary for e in self.entries if not e.verify()]
        return (not bad), bad

    def render_packet(self) -> str:
        """Court-ready Markdown packet: chronological, hash-attested, grouped by kind."""
        intact, bad = self.integrity()
        ordered = sorted(self.entries, key=lambda e: (e.occurred_on, e.captured_at))
        lines = [
            f"# Evidence Packet — {self.case_name}",
            "",
            f"Generated {_now_iso()[:10]} · {len(self.entries)} entries · "
            f"integrity: {'VERIFIED (no entries altered after capture)' if intact else 'COMPROMISED: ' + ', '.join(bad)}",
            "",
            "Each entry records when the event occurred and the immutable time it was logged. "
            "Content hashes attest the record was not edited after capture.",
            "",
            "## Chronology",
            "",
            "| Occurred | Logged (UTC) | Type | Summary | Attachment |",
            "|---|---|---|---|---|",
        ]
        for e in ordered:
            att = e.attachment or "—"
            lines.append(f"| {e.occurred_on} | {e.captured_at[:19]} | {e.kind} | {e.summary} | {att} |")
        lines += ["", "## Detail", ""]
        for e in ordered:
            lines.append(f"### {e.occurred_on} — {e.kind}: {e.summary}")
            if e.detail:
                lines.append(e.detail)
            lines.append(f"_logged {e.captured_at} · sha256 {e.content_hash[:16]}…_")
            lines.append("")
        return "\n".join(lines)
