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
        stocks, _bm, used_fallback = fetch_prices_with_fallback(
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


# ── Date range semantics ─────────────────────────────────────────────────────


def _yf_like(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Mimic yfinance, whose own `end` is exclusive."""
    dates = pd.bdate_range(start, pd.Timestamp(end) - pd.Timedelta(days=1))
    frame = pd.DataFrame(
        {t: np.arange(100.0, 100.0 + len(dates)) for t in tickers}, index=dates
    )
    frame.columns = pd.MultiIndex.from_arrays([["Close"] * len(tickers), tickers])
    return frame


@patch("keep_rollin.data.yf.download")
def test_end_date_is_inclusive(mock_dl):
    """The end date is the last bar analysed, unlike yfinance's own convention."""
    mock_dl.side_effect = lambda t, start, end, **k: _yf_like(list(t), start, end)

    stocks, _ = fetch_prices(["AAA"], "BBB", "2023-06-01", "2023-06-15")

    assert stocks.index.max() == pd.Timestamp("2023-06-15")


@patch("keep_rollin.data.yf.download")
def test_upstream_is_asked_for_one_extra_day(mock_dl):
    mock_dl.side_effect = lambda t, start, end, **k: _yf_like(list(t), start, end)

    fetch_prices(["AAA"], "BBB", "2023-06-01", "2023-06-15")

    assert mock_dl.call_args.kwargs["end"] == "2023-06-16"
    assert mock_dl.call_args.kwargs["start"] == "2023-06-01"


@patch("keep_rollin.data.yf.download")
def test_live_and_fallback_agree_on_the_last_bar(mock_dl):
    """Regression: the fallback was inclusive while the live path was exclusive,
    so an outage silently shifted the window by a day."""
    mock_dl.side_effect = lambda t, start, end, **k: _yf_like(list(t), start, end)

    live, _ = fetch_prices(
        FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2023-06-01", "2023-06-15"
    )
    offline, _ = load_fallback_prices(
        FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2023-06-01", "2023-06-15"
    )

    assert live.index.max() == offline.index.max()


@patch("keep_rollin.data.yf.download")
def test_default_range_ends_on_the_previous_trading_day(mock_dl):
    """Composing the default end with inclusivity must not lose a day."""
    mock_dl.side_effect = lambda t, start, end, **k: _yf_like(list(t), start, end)

    start, end = default_date_range()
    stocks, _ = fetch_prices(FALLBACK_TICKERS, FALLBACK_BENCHMARK, str(start), str(end))

    assert stocks.index.max().date() == previous_trading_day()


# ── Partial upstream responses ───────────────────────────────────────────────


@patch("keep_rollin.data.yf.download")
def test_missing_benchmark_falls_back_instead_of_reporting_blanks(mock_dl):
    """Regression: assets can arrive while the benchmark does not.

    Nothing raises and the stock frame is non-empty, so the old guard treated
    it as a successful live fetch — leaving every excess return undefined and
    the dashboard reporting "no ranked result" with no explanation.
    """
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            FALLBACK_TICKERS[0]: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n)),
            FALLBACK_TICKERS[1]: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n)),
            FALLBACK_BENCHMARK: np.full(n, np.nan),
        },
        index=dates,
    )
    frame.columns = pd.MultiIndex.from_arrays(
        [["Close"] * 3, [*FALLBACK_TICKERS, FALLBACK_BENCHMARK]]
    )
    mock_dl.return_value = frame

    with pytest.warns(UserWarning, match="benchmark"):
        stocks, bench, used_fallback = fetch_prices_with_fallback(
            FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2023-01-01", "2023-12-31"
        )

    assert used_fallback is True, "a blank benchmark must not pass as live data"
    assert not bench.empty
    assert not stocks.empty


@patch("keep_rollin.data.yf.download")
def test_missing_assets_still_falls_back(mock_dl):
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    frame = pd.DataFrame(
        {
            FALLBACK_TICKERS[0]: np.full(n, np.nan),
            FALLBACK_TICKERS[1]: np.full(n, np.nan),
            FALLBACK_BENCHMARK: np.arange(100.0, 100.0 + n),
        },
        index=dates,
    )
    frame.columns = pd.MultiIndex.from_arrays(
        [["Close"] * 3, [*FALLBACK_TICKERS, FALLBACK_BENCHMARK]]
    )
    mock_dl.return_value = frame

    with pytest.warns(UserWarning, match="assets"):
        _, _, used_fallback = fetch_prices_with_fallback(
            FALLBACK_TICKERS, FALLBACK_BENCHMARK, "2023-01-01", "2023-12-31"
        )

    assert used_fallback is True
