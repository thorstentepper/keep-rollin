from __future__ import annotations

import warnings
from importlib import resources
from typing import Sequence

import pandas as pd
import yfinance as yf

FALLBACK_PACKAGE = "keep_rollin.resources"
FALLBACK_RESOURCE = "fallback_prices.parquet"

# Two rows is the bare minimum for a single daily return; anything less is not
# a usable series, so a narrower slice falls back to the full snapshot.
_MIN_FALLBACK_ROWS = 2


class FallbackUnavailable(RuntimeError):
    """The bundled snapshot cannot serve the requested tickers."""


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
        End date in ``YYYY-MM-DD`` format (exclusive).

    Returns
    -------
    stock_prices:
        DataFrame of adjusted close prices, one column per ticker.
    benchmark_prices:
        Series of adjusted close prices for the benchmark.
    """
    all_tickers = list(tickers) + [benchmark]
    raw = yf.download(
        all_tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
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
        Optional ``YYYY-MM-DD`` bounds. If the overlap with the snapshot is
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
        if not stock_prices.empty:
            return stock_prices, benchmark_prices, False
        reason = "Yahoo Finance returned no rows"
    except Exception as exc:
        reason = f"Yahoo Finance request failed: {exc}"

    warnings.warn(f"{reason}; using bundled fallback snapshot", stacklevel=2)
    stock_prices, benchmark_prices = load_fallback_prices(
        tickers, benchmark, start, end
    )
    return stock_prices, benchmark_prices, True
