from __future__ import annotations

import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from keep_rollin.data import (
    FallbackUnavailable,
    default_date_range,
    fetch_prices,
    fetch_prices_with_fallback,
    load_fallback_prices,
    previous_trading_day,
)


def _make_yf_response(tickers: list[str], n: int = 10) -> pd.DataFrame:
    """Build a DataFrame that mimics yf.download output for multiple tickers."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    data = {t: 100.0 + np.arange(n, dtype=float) for t in tickers}
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_arrays([["Close"] * len(tickers), tickers])
    return df


@patch("keep_rollin.data.yf.download")
def test_stock_columns_match_requested_tickers(mock_dl):
    tickers = ["MSFT", "NVDA"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    stocks, _ = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert list(stocks.columns) == tickers


@patch("keep_rollin.data.yf.download")
def test_benchmark_returned_as_series(mock_dl):
    tickers = ["MSFT"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    _, bm = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert isinstance(bm, pd.Series)


@patch("keep_rollin.data.yf.download")
def test_download_receives_all_tickers(mock_dl):
    tickers = ["MSFT", "NVDA"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    called_with = mock_dl.call_args[0][0]
    assert set(called_with) == set(tickers + [benchmark])


@patch("keep_rollin.data.yf.download")
def test_output_contains_no_na(mock_dl):
    tickers = ["MSFT", "NVDA"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    stocks, bm = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert not stocks.isna().any().any()
    assert not bm.isna().any()


@patch("keep_rollin.data.yf.download")
def test_stock_and_benchmark_share_index(mock_dl):
    tickers = ["MSFT"]
    benchmark = "^GSPC"
    mock_dl.return_value = _make_yf_response(tickers + [benchmark])
    stocks, bm = fetch_prices(tickers, benchmark, "2020-01-01", "2020-12-31")
    assert stocks.index.equals(bm.index)


# ── Default dates ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "reference, expected",
    [
        ("2026-08-18", "2026-08-17"),  # Tuesday -> Monday
        ("2026-08-17", "2026-08-14"),  # Monday -> previous Friday
        ("2026-08-16", "2026-08-14"),  # Sunday -> Friday, not Thursday
        ("2026-08-15", "2026-08-14"),  # Saturday -> Friday
        ("2026-08-14", "2026-08-13"),  # Friday -> Thursday
    ],
)
def test_previous_trading_day_skips_weekends(reference, expected):
    got = previous_trading_day(datetime.date.fromisoformat(reference))
    assert got == datetime.date.fromisoformat(expected)


def test_previous_trading_day_returns_a_date():
    assert isinstance(previous_trading_day(datetime.date(2026, 8, 18)), datetime.date)


def test_previous_trading_day_is_strictly_before_reference():
    reference = datetime.date(2026, 8, 18)
    assert previous_trading_day(reference) < reference


def test_previous_trading_day_defaults_to_today():
    assert previous_trading_day() < datetime.date.today()


def test_default_range_spans_five_years_to_previous_trading_day():
    start, end = default_date_range(datetime.date(2026, 8, 18))
    assert end == datetime.date(2026, 8, 17)
    assert start == datetime.date(2021, 8, 17)


def test_default_range_years_is_adjustable():
    start, end = default_date_range(datetime.date(2026, 8, 18), years=1)
    assert (end - start).days == 365


def test_default_range_handles_leap_day():
    """29 February has no counterpart five years earlier, so the start rolls back."""
    # Friday 1 March 2024 -> previous trading day is Thursday 29 February.
    start, end = default_date_range(datetime.date(2024, 3, 1))
    assert end == datetime.date(2024, 2, 29)
    assert start == datetime.date(2019, 2, 28)


# ── Offline fallback ─────────────────────────────────────────────────────────

FALLBACK_TICKERS = ["MSFT", "NVDA"]
FALLBACK_BENCHMARK = "^GSPC"


def test_fallback_snapshot_is_shipped_and_loadable():
    stocks, bm = load_fallback_prices(FALLBACK_TICKERS, FALLBACK_BENCHMARK)
    assert list(stocks.columns) == FALLBACK_TICKERS
    assert isinstance(bm, pd.Series)
    assert not stocks.empty


def test_fallback_rejects_symbols_it_cannot_serve():
    with pytest.raises(FallbackUnavailable):
        load_fallback_prices(["NOT_A_TICKER"], FALLBACK_BENCHMARK)


def test_fallback_clips_to_requested_range():
    full, _ = load_fallback_prices(FALLBACK_TICKERS, FALLBACK_BENCHMARK)
    start = full.index[10].strftime("%Y-%m-%d")
    end = full.index[40].strftime("%Y-%m-%d")
    clipped, _ = load_fallback_prices(FALLBACK_TICKERS, FALLBACK_BENCHMARK, start, end)
    assert len(clipped) < len(full)
    assert clipped.index.min() >= pd.Timestamp(start)
    assert clipped.index.max() <= pd.Timestamp(end)


def test_fallback_ignores_range_with_no_usable_overlap():
    """A range outside the snapshot returns the full snapshot, not an empty frame."""
    stocks, _ = load_fallback_prices(
        FALLBACK_TICKERS, FALLBACK_BENCHMARK, "1990-01-01", "1990-06-01"
    )
    assert not stocks.empty


@patch("keep_rollin.data.yf.download")
def test_live_fetch_reports_no_fallback(mock_dl):
    mock_dl.return_value = _make_yf_response(FALLBACK_TICKERS + [FALLBACK_BENCHMARK])
    _, _, used_fallback = fetch_prices_with_fallback(
        FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2020-01-01", "2020-12-31"
    )
    assert used_fallback is False


@patch("keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited"))
def test_download_error_falls_back_to_snapshot(mock_dl):
    with pytest.warns(UserWarning, match="fallback"):
        stocks, bm, used_fallback = fetch_prices_with_fallback(
            FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2020-01-01", "2020-12-31"
        )
    assert used_fallback is True
    assert not stocks.empty
    assert list(stocks.columns) == FALLBACK_TICKERS


@patch("keep_rollin.data.yf.download")
def test_empty_download_falls_back_to_snapshot(mock_dl):
    empty = _make_yf_response(FALLBACK_TICKERS + [FALLBACK_BENCHMARK], n=0)
    mock_dl.return_value = empty
    with pytest.warns(UserWarning, match="fallback"):
        stocks, _, used_fallback = fetch_prices_with_fallback(
            FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2020-01-01", "2020-12-31"
        )
    assert used_fallback is True
    assert not stocks.empty


@patch("keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited"))
def test_unservable_symbols_raise_rather_than_invent_data(mock_dl):
    with pytest.raises(FallbackUnavailable), pytest.warns(UserWarning):
        fetch_prices_with_fallback(
            ["NOT_A_TICKER"], FALLBACK_BENCHMARK, "2020-01-01", "2020-12-31"
        )
