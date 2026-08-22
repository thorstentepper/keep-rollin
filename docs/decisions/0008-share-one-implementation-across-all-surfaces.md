# 0008. Share one implementation across all surfaces

**Status:** Accepted — 2026-08-15
**Decision:** Keep the metrics, defaults and validation bounds in the package
core, and have the CLI, the dashboard and the HTTP API call into it rather
than reimplement any of it.

## Context

Adding a FastAPI layer made three interfaces over the same calculations. The
CLI and the dashboard had already drifted: both built the same results table
independently, so a change to one silently left the other behind. A third copy
would have made divergence certain.

## Considered options

- **One shared core; surfaces only present** — chosen. `summarise()` produces
  the results table, defaults and rolling-window bounds are module constants,
  and every surface imports them.
- **Reimplement per surface** — rejected. Each interface stays simpler in
  isolation, at the cost of them disagreeing about what the same request
  means.

## Consequences

- A bare `rollin` and a bare `GET /metrics` return the same numbers over the
  same window, and a test asserts it.
- Contract differences become visible as bugs rather than as opinions: the CLI
  requiring dates the API defaulted, and accepting a rolling window the API
  rejected, were both found this way and fixed by pointing them at the same
  constants.
- Presentation choices must stay out of the core. Where a surface needs its
  own wording — the explanation for an undefined ranking, for instance — the
  string is a shared constant so all three say the same thing.
