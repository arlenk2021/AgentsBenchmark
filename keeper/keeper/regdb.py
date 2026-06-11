"""Regulation database — the messy-source -> verified-structured-DB layer.

keeper's engineering thesis (from the market analysis): CDFW rules live in dense PDFs
and Title 14 sections that are unusable in the field. The value is parsing them into a
verified, structured, OFFLINE database with provenance on every rule. This module loads
that DB and exposes typed lookups; it holds no network dependency, so it works at the
lake with no signal.

Every `Rule` carries `verified_on` and a `citation`. A rule whose verification is stale
is surfaced (not silently trusted) — the same drift discipline as wrodium-bench.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    region: str
    min_size_in: float | None
    max_size_in: float | None
    daily_bag: int | None
    season: str
    citation: str
    verified_on: str
    season_note: str | None = None
    possession: int | None = None


@dataclass(frozen=True)
class Species:
    key: str
    common_names: tuple[str, ...]
    scientific: str
    measure: str
    rules: tuple[Rule, ...]

    def matches(self, name: str) -> bool:
        n = name.strip().lower()
        return n == self.key or n in self.common_names or any(n in cn or cn in n for cn in self.common_names)

    def rule_for(self, region: str | None) -> Rule | None:
        if region:
            for r in self.rules:
                if r.region == region:
                    return r
        # Fall back to a statewide/default rule if region not specified or not found.
        for r in self.rules:
            if "statewide" in r.region or "default" in r.region:
                return r
        return self.rules[0] if self.rules else None


@dataclass
class RegDB:
    jurisdiction: str
    domain: str
    source: dict
    species: list[Species]

    @classmethod
    def load(cls, path: str | Path) -> "RegDB":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        species = []
        for s in d.get("species", []):
            rules = tuple(
                Rule(
                    region=r["region"], min_size_in=r.get("min_size_in"),
                    max_size_in=r.get("max_size_in"), daily_bag=r.get("daily_bag"),
                    season=r.get("season", "unknown"), citation=r.get("citation", ""),
                    verified_on=r.get("verified_on", "1970-01-01"),
                    season_note=r.get("season_note"), possession=r.get("possession"),
                )
                for r in s.get("rules", [])
            )
            species.append(Species(
                key=s["key"], common_names=tuple(n.lower() for n in s.get("common_names", [])),
                scientific=s.get("scientific", ""), measure=s.get("measure", "total_length_in"),
                rules=rules,
            ))
        return cls(d.get("jurisdiction", "?"), d.get("domain", "?"), d.get("source", {}), species)

    @classmethod
    def load_dir(cls, directory: str | Path) -> "RegDB":
        """Merge every *.json regulation file in a directory into one DB."""
        directory = Path(directory)
        merged: RegDB | None = None
        for f in sorted(directory.glob("*.json")):
            db = cls.load(f)
            if merged is None:
                merged = RegDB(db.jurisdiction, "combined", {"files": []}, [])
            merged.species.extend(db.species)
            merged.source.setdefault("files", []).append(str(f.name))
        if merged is None:
            raise FileNotFoundError(f"no regulation json found in {directory}")
        return merged

    def find(self, name: str) -> Species | None:
        return next((s for s in self.species if s.matches(name)), None)

    def stale_rules(self, as_of: str, *, max_age_days: int = 365) -> list[tuple[str, Rule]]:
        """Rules not re-verified within max_age_days (fishing rules change annually)."""
        cutoff = _dt.date.fromisoformat(as_of) - _dt.timedelta(days=max_age_days)
        out = []
        for sp in self.species:
            for r in sp.rules:
                if _dt.date.fromisoformat(r.verified_on) < cutoff:
                    out.append((sp.key, r))
        return out
