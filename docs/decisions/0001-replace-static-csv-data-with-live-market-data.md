# 0001. Replace static CSV data with live market data

**Status:** Accepted — 2026-05-16
**Decision:** Fetch prices from Yahoo Finance at runtime instead of shipping
the CSV files the original exercise came with.

## Context

The project began as a DataCamp exercise built around two bundled CSV files
covering a fixed set of tickers and a fixed date range. Every interesting
question — a different asset, a different period, a different benchmark —
required editing the data rather than the arguments.

## Considered options

- **Fetch from Yahoo Finance via `yfinance`** — chosen. Any ticker and any
  date range become parameters, which is what turns a finished exercise into
  a tool.
- **Keep the bundled CSVs** — rejected. Reproducible and offline, but the
  analysis is then permanently about someone else's chosen assets.
- **Bundle CSVs and allow an override** — rejected as the worst of both: two
  code paths to maintain from the outset, for a fallback nothing yet needed.

## Consequences

- The project now depends on a third-party endpoint that rate-limits, can be
  slow, and has changed its response shape before. Everything downstream —
  the offline snapshot in [0007](0007-ship-an-offline-price-snapshot-as-a-fallback.md),
  the explicit request timeout, the caching in
  [0012](0012-cache-price-fetches-but-never-cache-fallback-results.md) —
  exists because of this decision.
- Results are no longer reproducible from the repository alone: the same
  command run on two dates returns different numbers.
- Tests must mock the network, or they flake.
