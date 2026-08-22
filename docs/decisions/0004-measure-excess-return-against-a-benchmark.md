# 0004. Measure excess return against a benchmark

**Status:** Accepted — 2026-05-16
**Decision:** Compute Sharpe and Sortino on returns in excess of a
configurable benchmark rather than a risk-free rate, annualised with a
252-trading-day year.

## Context

The Sharpe ratio is classically defined on returns in excess of the risk-free
rate. This project instead subtracts the returns of a benchmark symbol, which
makes the result closer to an information ratio than to a textbook Sharpe
ratio. That difference is invisible in the output and is the first thing a
finance-literate reader asks about.

## Considered options

- **Excess over a configurable benchmark** — chosen. It answers the question
  the tool is actually for: did this asset beat the thing you would otherwise
  have held, per unit of risk taken? The benchmark is any Yahoo Finance
  symbol, so an index, a sector ETF and a competitor are all valid, and the
  same tooling covers index-relative and relative-value analysis.
- **Excess over a risk-free rate** — rejected. Textbook-correct, but it needs
  a rate series the project does not otherwise fetch, and it answers a
  question about absolute risk-adjusted return that the benchmark input
  already implies is not the point.

## Consequences

- Figures are not comparable to Sharpe ratios quoted elsewhere. The README
  states the convention up front so the difference is deliberate rather than
  discovered.
- Benchmarking an asset against itself yields excess returns of exactly zero,
  so the ratios are undefined — a real input that must degrade gracefully
  rather than crash.
- Max drawdown is computed on prices, not excess returns, so one column of
  the results table is benchmark-independent while the rest are not.
- Annualisation is fixed at 252 trading days; the constant is shared so no
  surface can disagree with the maths.
