"""Annualised risk/return metrics for multi-asset portfolios.

Computes Sharpe ratio, Sortino ratio, max drawdown, and rolling variants
against a configurable benchmark, using live data from Yahoo Finance.
"""

from keep_rollin.data import fetch_prices
from keep_rollin.metrics import (
    daily_returns,
    excess_returns,
    sharpe_ratio,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    sortino_ratio,
    max_drawdown,
)

__all__ = [
    "fetch_prices",
    "daily_returns",
    "excess_returns",
    "sharpe_ratio",
    "rolling_sharpe_ratio",
    "rolling_sortino_ratio",
    "sortino_ratio",
    "max_drawdown",
]
