# 0010. Default to five years ending on the previous trading day

**Status:** Accepted — 2026-08-15
**Decision:** Default to MSFT and NVDA against the S&P 500 over the five years
ending on the previous trading day, approximating trading days as weekdays.

## Context

Every surface needs a sensible starting point: the dashboard opens on
something before the user types anything, and a bare CLI or API call has to
mean something ([0008](0008-share-one-implementation-across-all-surfaces.md)).
A fixed date range would age; a range ending today would include a partial or
missing session.

## Considered options

- **Rolling window ending on the previous trading day** — chosen. Always
  current, always a completed session, and computed once in the core so every
  surface agrees.
- **A fixed historical range** — rejected. Stable and reproducible, but it
  silently becomes a dated example.
- **Ending today** — rejected. Today's bar is absent or incomplete depending
  on the hour.

## Considered options for "trading day"

- **Weekday arithmetic** — chosen. `numpy.busday_offset` with forward rolling,
  so a weekend resolves to the preceding Friday rather than overshooting to
  Thursday.
- **A real exchange calendar** — rejected. It means a dependency and a
  per-exchange calendar to keep current, to avoid an error whose entire cost
  is that a holiday returns no row.

## Consequences

- Defaults move with the calendar, so anything asserting them must derive the
  expected dates rather than hardcode them. A test that hardcoded them passed
  for four days and then failed.
- On an exchange holiday the default end date names a non-session; the data
  source simply returns no row for it.
- Five years of history means the 252-day rolling window produces a useful
  series rather than a single point.
