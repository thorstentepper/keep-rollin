from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sharpe_ratio.metrics import (
    daily_returns,
    excess_returns,
    max_drawdown,
    rolling_sharpe_ratio,
    sharpe_ratio,
    sortino_ratio,
)


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-01", periods=252, freq="B")
    ret_a = rng.normal(0.001, 0.01, 252)
    ret_b = rng.normal(0.0005, 0.015, 252)
    return pd.DataFrame(
        {"A": 100 * (1 + ret_a).cumprod(), "B": 100 * (1 + ret_b).cumprod()},
        index=dates,
    )


@pytest.fixture
def benchmark_prices(sample_prices: pd.DataFrame) -> pd.Series:
    rng = np.random.default_rng(99)
    ret = rng.normal(0.0003, 0.008, len(sample_prices))
    return pd.Series(
        100 * (1 + ret).cumprod(), index=sample_prices.index, name="BM"
    )


@pytest.fixture
def excess(sample_prices: pd.DataFrame, benchmark_prices: pd.Series) -> pd.DataFrame:
    return excess_returns(daily_returns(sample_prices), daily_returns(benchmark_prices))


class TestDailyReturns:
    def test_shape(self, sample_prices):
        ret = daily_returns(sample_prices)
        assert ret.shape == (len(sample_prices) - 1, sample_prices.shape[1])

    def test_no_na(self, sample_prices):
        assert not daily_returns(sample_prices).isna().any().any()

    def test_correct_values(self):
        prices = pd.DataFrame({"X": [100.0, 110.0, 99.0]})
        ret = daily_returns(prices)
        assert abs(ret["X"].iloc[0] - 0.10) < 1e-10
        assert abs(ret["X"].iloc[1] - (99 / 110 - 1)) < 1e-10


class TestExcessReturns:
    def test_shape(self, excess, sample_prices):
        assert excess.shape[1] == sample_prices.shape[1]

    def test_subtracts_correctly(self):
        dates = pd.date_range("2020-01-01", periods=3, freq="B")
        stock_ret = pd.DataFrame({"A": [0.01, 0.02, -0.01]}, index=dates)
        bench_ret = pd.Series([0.005, 0.005, 0.005], index=dates)
        exc = excess_returns(stock_ret, bench_ret)
        for actual, expected in zip(exc["A"], [0.005, 0.015, -0.015]):
            assert abs(actual - expected) < 1e-10


class TestSharpeRatio:
    def test_returns_series(self, excess):
        assert isinstance(sharpe_ratio(excess), pd.Series)

    def test_positive_for_upward_trend(self):
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        exc = pd.DataFrame({"A": [0.001] * 252}, index=dates)
        assert sharpe_ratio(exc)["A"] > 0

    def test_annualisation_factor(self):
        rng = np.random.default_rng(0)
        vals = rng.normal(0.001, 0.01, 252)
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        exc = pd.DataFrame({"A": vals}, index=dates)
        expected = vals.mean() / vals.std(ddof=1) * np.sqrt(252)
        assert abs(sharpe_ratio(exc)["A"] - expected) < 1e-10


class TestRollingSharpeRatio:
    def test_shape(self, excess):
        assert rolling_sharpe_ratio(excess, window=63).shape == excess.shape

    def test_leading_values_are_nan(self, excess):
        rolling = rolling_sharpe_ratio(excess, window=63)
        assert rolling.iloc[:62].isna().all().all()

    def test_values_after_window_are_finite(self, excess):
        rolling = rolling_sharpe_ratio(excess, window=63)
        assert rolling.iloc[63:].notna().all().all()


class TestSortinoRatio:
    def test_returns_series(self, excess):
        sr = sortino_ratio(excess)
        assert isinstance(sr, pd.Series)
        assert list(sr.index) == list(excess.columns)

    def test_exceeds_sharpe_for_positive_drift(self):
        """Sortino > Sharpe when drift is positive: downside semi-dev < total std."""
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", periods=252, freq="B")
        exc = pd.DataFrame({"A": rng.normal(0.001, 0.01, 252)}, index=dates)
        assert sortino_ratio(exc)["A"] >= sharpe_ratio(exc)["A"]


class TestMaxDrawdown:
    def test_returns_series(self, sample_prices):
        assert isinstance(max_drawdown(sample_prices), pd.Series)

    def test_always_nonpositive(self, sample_prices):
        assert (max_drawdown(sample_prices) <= 0).all()

    def test_within_valid_range(self, sample_prices):
        assert (max_drawdown(sample_prices) >= -1).all()

    def test_monotone_decline(self):
        """A steadily declining asset should match the total fractional loss."""
        prices = pd.DataFrame({"A": [100.0, 90.0, 80.0, 70.0]})
        expected = (70 - 100) / 100  # -0.30
        assert abs(max_drawdown(prices)["A"] - expected) < 1e-10
