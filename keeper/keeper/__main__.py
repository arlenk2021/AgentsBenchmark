"""`python -m keeper <species> [--size N] [--region R] [--kept N]` — field lookup.

Offline by design: loads the bundled verified DB and answers immediately, no network.
"""
from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

from .regdb import RegDB
from .decide import can_i_keep

DATA = Path(__file__).resolve().parents[1] / "data"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="keeper", description="Can I keep this fish? (CA, offline)")
    ap.add_argument("species", help="e.g. 'halibut', 'trout', 'abalone'")
    ap.add_argument("--size", type=float, help="measured length in inches")
    ap.add_argument("--region", help="e.g. north_of_point_sur")
    ap.add_argument("--kept", type=int, default=0, help="how many you've already kept today")
    ap.add_argument("--data", default=str(DATA), help="regulation data directory")
    args = ap.parse_args(argv)

    db = RegDB.load_dir(args.data)
    decision = can_i_keep(db, species=args.species, size_in=args.size, region=args.region,
                          already_kept=args.kept, as_of=_dt.date.today().isoformat())
    print(decision.render())
    return 0 if decision.verdict.value in ("keep", "release", "closed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
