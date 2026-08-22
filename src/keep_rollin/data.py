from __future__ import annotations

import datetime
import warnings
from collections.abc import Sequence
from importlib import resources

import numpy as np
import pandas as pd
import yfinance as yf

FALLBACK_PACKAGE = "keep_rollin.resources"
FALLBACK_RESOURCE = "fallback_prices.parquet"

#: Symbols analysed when the caller does not name any.
DEFAULT_TICKERS = ("MSFT", "NVDA")

#: Benchmark used when the caller does not name one (S&P 500).
DEFAULT_BENCHMARK = "^GSPC"

#: Years of history covered by the default analysis window.
DEFAULT_HISTORY_YEARS = 5

#: Per-request timeout for Yahoo Finance calls, in seconds.
#:
#: Set explicitly rather than inheriting yfinance's 10s default, which is an
#: upstream value we do not control. It is also deliberately more generous:
#: locally the default five-year fetch takes under two seconds, but a hosted
#: dashboard waking from sleep pays for a cold container and a shared egress
#: IP, and a request that times out there falls back to the offline snapshot
#: rather than showing live figures.
#:
#: Note this bounds each HTTP request, not the whole download: a multi-ticker
#: fetch issues several, so total wall time can exceed it.
FETCH_TIMEOUT_SECONDS = 20

# Two rows is the bare minimum for a single daily return; anything less is not
# a usable series, so a narrower slice falls back to the full snapshot.
_MIN_FALLBACK_ROWS = 2


class FallbackUnavailable(RuntimeError):
    """The bundled snapshot cannot serve the requested tickers."""


def previous_trading_day(reference: datetime.date | None = None) -> datetime.date:
    """The most recent trading day strictly before ``reference`` (default today).

    Trading days are approximated as weekdays. Exchange holidays are *not*
    excluded — pricing that in would mean shipping a market calendar per
    exchange. The cost of being wrong is one stale-by-a-day default, and
    Yahoo Finance simply returns no row for a holiday.

    Called on a weekend, this returns the preceding Friday rather than
    stepping a further day back.
    """
    ref = reference if reference is not None else datetime.date.today()
    # roll="forward" first moves a weekend onto Monday, so the -1 offset lands
    # on the Friday. roll="backward" would overshoot to the Thursday.
    result: datetime.date = np.busday_offset(ref, -1, roll="forward").astype(object)
    return result


def default_date_range(
    reference: datetime.date | None = None,
    years: int = DEFAULT_HISTORY_YEARS,
) -> tuple[datetime.date, datetime.date]:
    """Default analysis window: ``years`` of history to the previous trading day.

    Returns ``(start, end)``. Both bounds are inclusive, so ``end`` is the
    last trading day analysed.
    """
    end = previous_trading_day(reference)
    try:
        start = end.replace(year=end.year - years)
    except ValueError:
        # 29 February has no counterpart in a non-leap year.
        start = end.replace(year=end.year - years, day=28)
    return start, end


def fetch_prices(
    tickers: Sequence[str],
    benchmark: str,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.Series]:
    """Fetch adjusted daily close prices from Yahoo Finance.

    Parameters
    ----------
    tickers:
        Yahoo Finance symbols for the assets to analyse.
    benchmark:
        Yahoo Finance symbol for the benchmark (e.g. ``"^GSPC"`` for S&P 500).
    start:
        Start date in ``YYYY-MM-DD`` format (inclusive).
    end:
        End date in ``YYYY-MM-DD`` format (inclusive).

    Returns
    -------
    stock_prices:
        DataFrame of adjusted close prices, one column per ticker.
    benchmark_prices:
        Series of adjusted close prices for the benchmark.
    """
    all_tickers = list(tickers) + [benchmark]
    # Yahoo Finance treats ``end`` as exclusive. This package's contract is
    # inclusive — the end date is the last bar analysed — which is what a date
    # picker implies and what the offline fallback already does, so ask
    # upstream for one day more.
    end_exclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        all_tickers,
        start=start,
        end=end_exclusive,
        auto_adjust=True,
        progress=False,
        timeout=FETCH_TIMEOUT_SECONDS,
    )
    close = raw["Close"]
    return close[list(tickers)].dropna(), close[benchmark].dropna()


def load_fallback_prices(
    tickers: Sequence[str],
    benchmark: str,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Load prices from the parquet snapshot shipped with the package.

    The snapshot covers a fixed set of symbols and dates (see
    ``scripts/refresh_fallback.py``). Requests it cannot serve raise
    ``FallbackUnavailable`` rather than returning partial or invented data.

    Parameters
    ----------
    tickers:
        Symbols to return. Must all be present in the snapshot.
    benchmark:
        Benchmark symbol. Must be present in the snapshot.
    start, end:
        Optional ``YYYY-MM-DD`` bounds, both inclusive. If the overlap is
        too short to compute returns, the full snapshot is returned instead —
        stale dates are more useful here than an empty frame.

    Returns
    -------
    stock_prices, benchmark_prices:
        Same shape as :func:`fetch_prices`.
    """
    source = resources.files(FALLBACK_PACKAGE) / FALLBACK_RESOURCE
    with resources.as_file(source) as path:
        if not path.is_file():
            raise FallbackUnavailable(
                f"no bundled snapshot at {path}; "
                "run scripts/refresh_fallback.py to create one"
            )
        frame = pd.read_parquet(path)

    wanted = [*tickers, benchmark]
    missing = [c for c in wanted if c not in frame.columns]
    if missing:
        raise FallbackUnavailable(
            f"bundled snapshot covers {list(frame.columns)}, cannot serve {missing}"
        )

    lower = pd.Timestamp(start) if start else None
    upper = pd.Timestamp(end) if end else None
    clipped = frame.loc[lower:upper]
    if len(clipped) >= _MIN_FALLBACK_ROWS:
        frame = clipped

    return frame[list(tickers)].dropna(), frame[benchmark].dropna()


def fetch_prices_with_fallback(
    tickers: Sequence[str],
    benchmark: str,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.Series, bool]:
    """Fetch live prices, falling back to the bundled snapshot on failure.

    Yahoo Finance is an unversioned third-party endpoint: it rate-limits, and
    its response shape has changed before. Rather than let the dashboard fail
    outright, fall back to the shipped snapshot so it always renders.

    Returns
    -------
    stock_prices, benchmark_prices, used_fallback:
        ``used_fallback`` is True when the data came from the snapshot, so
        callers can tell the user the figures are not live.
    """
    try:
        stock_prices, benchmark_prices = fetch_prices(tickers, benchmark, start, end)
        if not stock_prices.empty and not benchmark_prices.empty:
            return stock_prices, benchmark_prices, False
        # A partial response is the awkward case: the assets can arrive while
        # the benchmark does not, which raises nothing and leaves a non-empty
        # frame. Every excess return is then undefined, so treat it as a
        # failed fetch rather than reporting a table of blanks.
        missing = "assets" if stock_prices.empty else f"the benchmark {benchmark}"
        reason = f"Yahoo Finance returned no rows for {missing}"
    except Exception as exc:
        reason = f"Yahoo Finance request failed: {exc}"

    warnings.warn(f"{reason}; using bundled fallback snapshot", stacklevel=2)
    stock_prices, benchmark_prices = load_fallback_prices(
        tickers, benchmark, start, end
    )
    return stock_prices, benchmark_prices, True
