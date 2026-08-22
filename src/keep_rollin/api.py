"""HTTP API exposing the same metrics as the CLI.

Run it with::

    uv run uvicorn keep_rollin.api:app --reload

Interactive docs are then served at ``/docs``.

Endpoints are declared with ``def`` rather than ``async def`` on purpose: the
work behind them is a blocking network fetch followed by CPU-bound pandas
work, so FastAPI runs them in its threadpool instead of stalling the event
loop.
"""

from __future__ import annotations

import datetime
import math
import threading
import time
from collections import OrderedDict
from importlib import resources
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from keep_rollin.data import (
    DEFAULT_BENCHMARK,
    DEFAULT_HISTORY_YEARS,
    DEFAULT_TICKERS,
    FALLBACK_PACKAGE,
    FALLBACK_RESOURCE,
    FallbackUnavailable,
    default_date_range,
    fetch_prices_with_fallback,
)
from keep_rollin.metrics import (
    DEFAULT_ROLLING_WINDOW,
    MAX_ROLLING_WINDOW,
    MIN_ROLLING_WINDOW,
    NO_LEADER_EXPLANATION,
    leader,
    summarise,
)

#: How long a successful live fetch stays cached. Daily close prices do not
#: change intraday, so re-fetching per request only burns Yahoo Finance quota.
CACHE_TTL_SECONDS = 900

#: Fallback data is cached far more briefly, so the API returns to live figures
#: shortly after Yahoo Finance recovers instead of pinning a stale snapshot.
FALLBACK_CACHE_TTL_SECONDS = 60

#: Upper bound on cached entries, so an unbounded variety of ticker/date
#: combinations cannot grow the cache without limit.
CACHE_MAX_ENTRIES = 128

app = FastAPI(
    title="keep-rollin",
    version="0.1.0",
    summary="Annualised risk/return metrics for multi-asset portfolios",
)


class AssetMetrics(BaseModel):
    """Metrics for a single asset. Null means undefined for this data."""

    ticker: str
    sharpe: float | None = Field(description="Annualised Sharpe ratio")
    sortino: float | None = Field(description="Annualised Sortino ratio")
    max_drawdown: float | None = Field(
        description="Largest peak-to-trough decline, as a fraction (<= 0)"
    )
    avg_rolling_sharpe: float | None = Field(
        description="Mean of the rolling Sharpe ratio over the window"
    )
    avg_rolling_sortino: float | None = Field(
        description="Mean of the rolling Sortino ratio over the window"
    )


class MetricsResponse(BaseModel):
    """A full ``/metrics`` response: the request echoed back, plus results.

    The echoed request matters because every parameter is optional — a caller
    that sent none still learns which tickers and dates were used. ``assets``
    holds one entry per requested ticker, in request order.
    """

    benchmark: str
    start: datetime.date
    end: datetime.date
    rolling_window: int
    observations: int = Field(description="Number of price rows the metrics used")
    used_fallback: bool = Field(
        description=(
            "True when live data was unavailable and the bundled offline "
            "snapshot was used; figures are then not current"
        )
    )
    best_sharpe: str | None = Field(
        description="Ticker with the highest Sharpe ratio, if any is defined"
    )
    note: str | None = Field(
        default=None,
        description=(
            "Set when no ranking was possible, explaining why the metrics "
            "came back undefined"
        ),
    )
    assets: list[AssetMetrics]


class HealthResponse(BaseModel):
    """Liveness of the service, and whether it could serve data offline.

    ``fallback_available`` reports whether the bundled price snapshot is
    present and readable. A deployment missing it is still healthy, but would
    fail outright rather than degrade if Yahoo Finance became unreachable.
    """

    status: str
    fallback_available: bool


def _json_safe(value: float) -> float | None:
    """Map NaN and ±inf to null.

    Both occur legitimately here — a Sortino ratio is infinite when a window
    holds no negative returns, and rolling means are NaN before the window
    fills — and neither is representable in JSON.
    """
    number = float(value)
    return number if math.isfinite(number) else None


def _normalise_tickers(tickers: list[str]) -> list[str]:
    """Upper-case, strip, and de-duplicate while preserving request order."""
    seen: dict[str, None] = {}
    for raw in tickers:
        symbol = raw.strip().upper()
        if symbol:
            seen.setdefault(symbol, None)
    return list(seen)


# ── Price cache ──────────────────────────────────────────────────────────────
#
# Endpoints run in FastAPI's threadpool, so several requests touch this at
# once and every access is taken under a lock. The lock deliberately does not
# span the fetch itself: holding it across a network call would serialise all
# requests. The cost is that concurrent misses for the same key may each
# fetch once, which is cheaper than blocking every other caller.

_PriceBundle = tuple[pd.DataFrame, "pd.Series[float]", bool]
_CacheKey = tuple[tuple[str, ...], str, str, str]

_cache: OrderedDict[_CacheKey, tuple[float, _PriceBundle]] = OrderedDict()
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Drop every cached price bundle. Mainly for tests and manual refreshes."""
    with _cache_lock:
        _cache.clear()


def _cache_get(key: _CacheKey) -> _PriceBundle | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at <= now:
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return payload


def _cache_put(key: _CacheKey, payload: _PriceBundle, ttl: float) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic() + ttl, payload)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)


def _fetch_cached(
    symbols: list[str],
    benchmark: str,
    start: datetime.date,
    end: datetime.date,
) -> tuple[_PriceBundle, bool]:
    """Return prices for this request plus whether they came from the cache.

    The cache holds the price fetch rather than the finished response, so
    requests differing only in ``rolling_window`` share one upstream call.
    Cached frames are treated as read-only; ``summarise`` never mutates them.
    """
    key = (tuple(symbols), benchmark, str(start), str(end))

    cached = _cache_get(key)
    if cached is not None:
        return cached, True

    bundle = fetch_prices_with_fallback(symbols, benchmark, str(start), str(end))
    used_fallback = bundle[2]
    _cache_put(
        key,
        bundle,
        FALLBACK_CACHE_TTL_SECONDS if used_fallback else CACHE_TTL_SECONDS,
    )
    return bundle, False


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe that also reports whether the offline snapshot is usable."""
    try:
        source = resources.files(FALLBACK_PACKAGE) / FALLBACK_RESOURCE
        with resources.as_file(source) as path:
            fallback_available = path.is_file()
    except (ModuleNotFoundError, FileNotFoundError):
        fallback_available = False

    return HealthResponse(status="ok", fallback_available=fallback_available)


@app.get("/metrics", response_model=MetricsResponse)
def metrics(
    response: Response,
    tickers: Annotated[
        list[str] | None,
        Query(
            description=(
                "Yahoo Finance symbols; repeat the parameter for several. "
                f"Defaults to {', '.join(DEFAULT_TICKERS)}."
            ),
            examples=[list(DEFAULT_TICKERS)],
        ),
    ] = None,
    start: Annotated[
        datetime.date | None,
        Query(
            description=(
                "Start date, inclusive, as YYYY-MM-DD. Defaults to "
                f"{DEFAULT_HISTORY_YEARS} years before the end date."
            ),
            examples=["2023-01-01"],
        ),
    ] = None,
    end: Annotated[
        datetime.date | None,
        Query(
            description=(
                "End date, inclusive, as YYYY-MM-DD. Defaults to the previous "
                "trading day."
            ),
            examples=["2024-01-01"],
        ),
    ] = None,
    benchmark: Annotated[
        str, Query(description="Benchmark symbol")
    ] = DEFAULT_BENCHMARK,
    rolling_window: Annotated[
        int,
        Query(
            ge=MIN_ROLLING_WINDOW,
            le=MAX_ROLLING_WINDOW,
            description="Rolling window in trading days (63 ≈ one quarter)",
        ),
    ] = DEFAULT_ROLLING_WINDOW,
) -> MetricsResponse:
    """Compute Sharpe, Sortino, max drawdown and rolling averages per asset.

    Every parameter is optional: with none supplied this reports the default
    tickers over the default window, so ``GET /metrics`` is a usable request.
    """
    # Each date defaults independently, so supplying only one still gives a
    # sensible window rather than requiring both or neither.
    default_start, default_end = default_date_range()
    if end is None:
        end = default_end
    if start is None:
        start = default_start

    symbols = _normalise_tickers(list(DEFAULT_TICKERS) if tickers is None else tickers)
    if not symbols:
        raise HTTPException(status_code=422, detail="No usable ticker symbols given.")
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start.")

    try:
        (
            (
                stock_prices,
                benchmark_prices,
                used_fallback,
            ),
            cache_hit,
        ) = _fetch_cached(symbols, benchmark, start, end)
    except FallbackUnavailable as exc:
        # Either the upstream is down, or it is up but does not know these
        # symbols; from here the two are indistinguishable, so say neither.
        raise HTTPException(
            status_code=503,
            detail=f"No price data available for {symbols} vs {benchmark}: {exc}",
        ) from exc

    if stock_prices.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No price rows for {symbols} between {start} and {end}.",
        )

    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"

    summary = summarise(stock_prices, benchmark_prices, window=rolling_window)

    best_sharpe = leader(summary["sharpe"])

    assets = [
        AssetMetrics(
            ticker=str(ticker),
            **{column: _json_safe(row[column]) for column in summary.columns},
        )
        for ticker, row in summary.iterrows()
    ]

    return MetricsResponse(
        benchmark=benchmark,
        start=start,
        end=end,
        rolling_window=rolling_window,
        observations=len(stock_prices),
        used_fallback=used_fallback,
        best_sharpe=best_sharpe,
        note=None if best_sharpe else NO_LEADER_EXPLANATION,
        assets=assets,
    )
