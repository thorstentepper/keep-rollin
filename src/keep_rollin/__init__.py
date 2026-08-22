"""Annualised risk/return metrics for multi-asset portfolios.

Computes Sharpe ratio, Sortino ratio, max drawdown, and rolling variants
against a configurable benchmark, using live data from Yahoo Finance.
"""

from keep_rollin.data import (
    FallbackUnavailable,
    fetch_prices,
    fetch_prices_with_fallback,
    load_fallback_prices,
)
from keep_rollin.metrics import (
    daily_returns,
    excess_returns,
    max_drawdown,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    sharpe_ratio,
    sortino_ratio,
    summarise,
)

__all__ = [
    "FallbackUnavailable",
    "daily_returns",
    "excess_returns",
    "fetch_prices",
    "fetch_prices_with_fallback",
    "load_fallback_prices",
    "max_drawdown",
    "rolling_sharpe_ratio",
    "rolling_sortino_ratio",
    "sharpe_ratio",
    "sortino_ratio",
    "summarise",
]
