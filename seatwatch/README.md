# seatwatch — course-seat availability alerts

Real-time alerts when a closed class opens up. Built **lean and honestly**: per the
product analysis this is the weakest *venture* wedge of the four — Coursicle already owns
the category (~2M students, bootstrapped, $4.99/semester), and the moat is **real-time
scraping + state-diffing + push**, NOT anti-hallucination. Included for portfolio breadth
and because the diff/notify core is a clean, testable piece of systems design.

## Honest framing

- The "why not an LLM" question **misframes** seatwatch: a chat model genuinely *can't*
  poll a registrar in real time — but that's a solved problem owned by an incumbent, not
  a new wedge.
- The only interesting differentiation is **registrar depth** (e.g. Berkeley CalCentral
  waitlist position, section-swap logic). That lives behind the `SeatSource` adapter
  interface — implement one per school; the diff/notify logic is school-agnostic.

## Architecture

No network code in the core. A real adapter implements `SeatSource.snapshot()`; the
deterministic `diff_snapshots()` computes seat-state transitions; a `Notifier` dispatches
the alert-worthy ones (open / seat freed / waitlist shrank). This keeps the valuable
logic unit-testable and isolates the scraping concerns.

```bash
cd seatwatch
python tests/test_seatwatch.py
```

```
seatwatch/
└── seatwatch/
    └── core.py   SeatSource adapter contract, diff_snapshots, Watcher, Notifier
```
