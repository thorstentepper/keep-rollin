from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from keep_rollin.data import fetch_prices


def _make_yf_response(tickers: list[str], n: int = 10) -> pd.DataFrame:
    """Build a DataFrame that mimics yf.download output for multiple tickers."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    data = {t: 100.0 + np.arange(n, dtype=float) for t in tickers}
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_arrays([["Close"] * len(tickers), tickers])
    return df


@patch("keep_rollin.data.yf.download")
def test_stock_columns_match_requested_tickers(mock_dl):
    tickers = ["AMZN", "META"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    stocks, _ = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert list(stocks.columns) == tickers


@patch("keep_rollin.data.yf.download")
def test_benchmark_returned_as_series(mock_dl):
    tickers = ["AMZN"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    _, bm = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert isinstance(bm, pd.Series)


@patch("keep_rollin.data.yf.download")
def test_download_receives_all_tickers(mock_dl):
    tickers = ["AMZN", "META"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    called_with = mock_dl.call_args[0][0]
    assert set(called_with) == set(tickers + [benchmark])


@patch("keep_rollin.data.yf.download")
def test_output_contains_no_na(mock_dl):
    tickers = ["AMZN", "META"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    stocks, bm = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert not stocks.isna().any().any()
    assert not bm.isna().any()


@patch("keep_rollin.data.yf.download")
def test_stock_and_benchmark_share_index(mock_dl):
    tickers = ["AMZN"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    stocks, bm = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert stocks.index.equals(bm.index)
