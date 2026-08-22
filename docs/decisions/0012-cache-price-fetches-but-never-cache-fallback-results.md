# 0012. Cache price fetches but never cache fallback results

**Status:** Accepted — 2026-08-16
**Decision:** Cache the upstream price fetch for fifteen minutes, and never
let a fallback result persist in that cache.

## Context

Daily closing prices do not change intraday, so refetching them per request
only spends rate limit. But the cache stores whatever the fetch returned,
including a fallback result — and a single failed fetch then pinned the
offline snapshot for the full cache lifetime.

That is not theoretical. The deployed dashboard served snapshot data for its
default tickers while any other ticker fetched live data happily, because the
default combination was one poisoned cache entry.

## Considered options

- **Cache the fetch; evict fallback results after use** — chosen. Repeat views
  stay off the rate limiter, while a transient failure self-corrects on the
  next request instead of persisting.
- **Cache everything uniformly** — rejected. This is the behaviour that caused
  the bug.
- **No caching** — rejected. Every interaction would hit the upstream endpoint,
  making rate limiting more likely, not less.

## Consequences

- Caching the fetch rather than the finished response means requests differing
  only in rolling window share one upstream call.
- The dashboard offers an explicit retry alongside the offline banner, so a
  user is never stuck waiting for a cache to expire.
- The API applies the same split with a short lifetime for fallback results
  and reports `X-Cache: HIT|MISS`.
- The cache is per process, so it is not shared across workers or replicas.
