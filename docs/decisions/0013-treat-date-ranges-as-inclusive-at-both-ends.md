# 0013. Treat date ranges as inclusive at both ends

**Status:** Accepted — 2026-08-16
**Decision:** Treat the end date as the last day analysed everywhere, asking
Yahoo Finance for one extra day to compensate for its exclusive end.

## Context

Yahoo Finance treats `end` as exclusive; pandas label slicing, used by the
offline snapshot, is inclusive. The project inherited both without choosing
between them, which produced two defects at once.

The live path and the offline path answered the same request differently: for
a range ending 15 June, live data stopped on the 14th and the snapshot
included the 15th. A Yahoo outage therefore shifted the analysis window by a
day, silently.

Composed with the default end date
([0010](0010-default-to-five-years-ending-on-the-previous-trading-day.md)),
exclusivity also meant the last bar in a default run was two trading days back
rather than one — the previous trading day was named as the end and then
excluded.

## Considered options

- **Inclusive everywhere** — chosen. It matches what a date picker implies,
  makes "previous trading day" mean the last bar analysed, and aligns the live
  and offline paths on the behaviour the snapshot already had.
- **Exclusive everywhere, documented loudly** — rejected. Less code, but it
  leaves a date field in a UI whose stated end is deliberately excluded, and
  the fallback still needed changing to match.

## Consequences

- `fetch_prices` adds a day before calling upstream. Anything reading that
  call directly sees the shifted value, so the adjustment is commented at the
  call site.
- The convention is stated once in the README and inherited by all three
  surfaces rather than restated per interface.
- Examples must be chosen carefully: a range ending 1 January only looked
  correct because New Year's Day is a holiday.
