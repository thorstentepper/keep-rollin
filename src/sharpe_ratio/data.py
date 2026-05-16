from __future__ import annotations

from typing import Sequence

import pandas as pd
import yfinance as yf


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
