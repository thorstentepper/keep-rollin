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


def max_drawdown(prices: pd.DataFrame) -> pd.Series:
    """Maximum peak-to-trough decline for each asset, expressed as a fraction (≤ 0)."""
    cumulative = (1 + prices.pct_change().fillna(0)).cumprod()
    rolling_max = cumulative.cummax()
    return ((cumulative - rolling_max) / rolling_max).min()
