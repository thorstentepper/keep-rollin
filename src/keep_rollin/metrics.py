from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Compute daily percentage returns, dropping the first NaN row."""
    return prices.pct_change().dropna()


def excess_returns(
    stock_returns: pd.DataFrame,
    benchmark_returns: pd.Series,
) -> pd.DataFrame:
    """Subtract benchmark returns from stock returns, aligning on the index."""
    return stock_returns.sub(benchmark_returns, axis=0).dropna()


def sharpe_ratio(excess: pd.DataFrame) -> pd.Series:
    """Annualised Sharpe ratio: mean excess return / std * sqrt(252)."""
    return excess.mean() / excess.std() * np.sqrt(TRADING_DAYS)


def rolling_sharpe_ratio(excess: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    """Sharpe ratio computed over a rolling window of trading days.

    Parameters
    ----------
    window:
        Number of trading days per window. Default 63 ≈ one quarter.
    """
    roll_mean = excess.rolling(window).mean()
    roll_std = excess.rolling(window).std()
    return roll_mean / roll_std * np.sqrt(TRADING_DAYS)


def sortino_ratio(excess: pd.DataFrame) -> pd.Series:
    """Annualised Sortino ratio: mean excess return / downside semi-deviation * sqrt(252).

    Downside semi-deviation is the root mean square of negative excess returns,
    which avoids penalising upside volatility the way Sharpe does.
    """
    mean = excess.mean()
    downside = np.sqrt((excess.clip(upper=0) ** 2).mean())
    return mean / downside * np.sqrt(TRADING_DAYS)


def rolling_sortino_ratio(excess: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    """Sortino ratio computed over a rolling window of trading days.

    Parameters
    ----------
    window:
        Number of trading days per window. Default 63 ≈ one quarter.

    Notes
    -----
    Downside semi-deviation is undefined when a window contains no negative
    returns, producing inf. This is more likely over short windows, so
    estimates are noisier than rolling Sharpe at the same window length.
    """
    roll_mean = excess.rolling(window).mean()
    downside = excess.clip(upper=0).pow(2).rolling(window).mean().pow(0.5)
    return roll_mean / downside * np.sqrt(TRADING_DAYS)


def max_drawdown(prices: pd.DataFrame) -> pd.Series:
    """Maximum peak-to-trough decline for each asset, expressed as a fraction (≤ 0)."""
    cumulative = (1 + prices.pct_change().fillna(0)).cumprod()
    rolling_max = cumulative.cummax()
    return ((cumulative - rolling_max) / rolling_max).min()


#: Column order of :func:`summarise`, using stable machine-readable names.
SUMMARY_COLUMNS = (
    "sharpe",
    "sortino",
    "max_drawdown",
    "avg_rolling_sharpe",
    "avg_rolling_sortino",
)


def summarise(
    stock_prices: pd.DataFrame,
    benchmark_prices: pd.Series,
    window: int = 63,
) -> pd.DataFrame:
    """Compute the full metrics table for a set of assets against a benchmark.

    This is the single definition of "the metrics" shared by the CLI, the
    Streamlit dashboard, and the HTTP API, so all three cannot drift apart.
    Values are unrounded; presentation layers round as they see fit.

    Parameters
    ----------
    stock_prices:
        Adjusted close prices, one column per asset.
    benchmark_prices:
        Adjusted close prices for the benchmark.
    window:
        Rolling window in trading days.

    Returns
    -------
    DataFrame indexed by ticker with the columns in :data:`SUMMARY_COLUMNS`.
    """
    stock_ret = daily_returns(stock_prices)
    bench_ret = daily_returns(benchmark_prices)
    exc = excess_returns(stock_ret, bench_ret)

    return pd.DataFrame(
        {
            "sharpe": sharpe_ratio(exc),
            "sortino": sortino_ratio(exc),
            "max_drawdown": max_drawdown(stock_prices),
            "avg_rolling_sharpe": rolling_sharpe_ratio(exc, window=window).mean(),
            "avg_rolling_sortino": rolling_sortino_ratio(exc, window=window).mean(),
        },
        columns=list(SUMMARY_COLUMNS),
    )
