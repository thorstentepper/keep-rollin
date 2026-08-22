from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from keep_rollin.cli import main

BENCHMARK = "^GSPC"


def _yf_frame(columns: dict[str, np.ndarray], n: int) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    frame = pd.DataFrame(columns, index=dates)
    frame.columns = pd.MultiIndex.from_arrays(
        [["Close"] * len(frame.columns), list(frame.columns)]
    )
    return frame


def _run(tickers: list[str]) -> None:
    main([*tickers, "--start", "2024-01-01", "--end", "2024-04-01"])


@patch("keep_rollin.data.yf.download")
def test_reports_the_leader_for_normal_data(mock_dl, capsys):
    n = 60
    rng = np.random.default_rng(0)
    mock_dl.return_value = _yf_frame(
        {
            "GOOD": 100 * np.cumprod(1 + rng.normal(0.002, 0.01, n)),
            BENCHMARK: np.full(n, 100.0),
        },
        n,
    )
    _run(["GOOD"])
    assert "Highest Sharpe ratio: GOOD" in capsys.readouterr().out


@patch("keep_rollin.data.yf.download")
def test_flat_series_explains_instead_of_crashing(mock_dl, capsys):
    """A price series that never moves leaves every metric undefined."""
    n = 60
    mock_dl.return_value = _yf_frame(
        {"FLAT": np.full(n, 100.0), BENCHMARK: np.full(n, 100.0)}, n
    )

    _run(["FLAT"])  # must not raise

    out = capsys.readouterr().out
    assert "No ranked result" in out
    assert "flat" in out
    assert "Highest Sharpe" not in out


@patch("keep_rollin.data.yf.download")
def test_one_good_ticker_among_degenerate_ones_still_ranks(mock_dl, capsys):
    n = 60
    rng = np.random.default_rng(1)
    mock_dl.return_value = _yf_frame(
        {
            "FLAT": np.full(n, 100.0),
            "GOOD": 100 * np.cumprod(1 + rng.normal(0.002, 0.01, n)),
            BENCHMARK: np.full(n, 100.0),
        },
        n,
    )
    _run(["FLAT", "GOOD"])

    out = capsys.readouterr().out
    assert "Highest Sharpe ratio: GOOD" in out
    assert "No ranked result" not in out


# ── Defaults ─────────────────────────────────────────────────────────────────


@patch("keep_rollin.data.yf.download")
def test_runs_with_no_arguments_at_all(mock_dl, capsys):
    """A bare `rollin` matches a bare GET /metrics: same tickers, same window."""
    from keep_rollin.data import DEFAULT_BENCHMARK, DEFAULT_TICKERS, default_date_range

    n = 300
    rng = np.random.default_rng(2)
    columns = {
        t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
        for t in [*DEFAULT_TICKERS, DEFAULT_BENCHMARK]
    }
    mock_dl.return_value = _yf_frame(columns, n)

    main([])  # must not raise

    out = capsys.readouterr().out
    start, end = default_date_range()
    for ticker in DEFAULT_TICKERS:
        assert ticker in out
    assert str(start) in out and str(end) in out


@patch("keep_rollin.data.yf.download")
def test_tickers_without_dates_use_the_default_window(mock_dl, capsys):
    from keep_rollin.data import default_date_range

    n = 300
    rng = np.random.default_rng(3)
    mock_dl.return_value = _yf_frame(
        {
            t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
            for t in ["AAPL", BENCHMARK]
        },
        n,
    )

    main(["AAPL"])

    start, end = default_date_range()
    out = capsys.readouterr().out
    assert str(start) in out and str(end) in out


@patch("keep_rollin.data.yf.download")
def test_lowercase_tickers_are_normalised(mock_dl, capsys):
    n = 300
    rng = np.random.default_rng(4)
    mock_dl.return_value = _yf_frame(
        {
            t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
            for t in ["AAPL", BENCHMARK]
        },
        n,
    )

    main(["  aapl  "])

    assert mock_dl.call_args[0][0] == ["AAPL", BENCHMARK]


@patch("keep_rollin.data.yf.download")
def test_explicit_dates_still_win(mock_dl, capsys):
    n = 300
    rng = np.random.default_rng(5)
    mock_dl.return_value = _yf_frame(
        {
            t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
            for t in ["AAPL", BENCHMARK]
        },
        n,
    )

    main(["AAPL", "--start", "2023-01-01", "--end", "2024-01-01"])

    assert "2023-01-01" in capsys.readouterr().out
    assert mock_dl.call_args.kwargs["start"] == "2023-01-01"


@patch("keep_rollin.data.yf.download")
def test_rolling_window_bounds_match_the_api(mock_dl, capsys):
    """The API rejects <2 and >252; the CLI must not quietly accept them."""
    import pytest

    from keep_rollin.metrics import MAX_ROLLING_WINDOW, MIN_ROLLING_WINDOW

    for bad in (MIN_ROLLING_WINDOW - 1, MAX_ROLLING_WINDOW + 1):
        with pytest.raises(SystemExit):
            main(["AAPL", "--rolling-window", str(bad)])
        assert "must be between" in capsys.readouterr().err


# ── Plotting ─────────────────────────────────────────────────────────────────


@patch("keep_rollin.cli.plt.show")
@patch("keep_rollin.data.yf.download")
def test_plot_flag_renders_both_charts(mock_dl, mock_show, capsys):
    """The --plot branch is otherwise untested, and a refactor once broke it."""
    import matplotlib.pyplot as plt

    n = 300
    rng = np.random.default_rng(6)
    mock_dl.return_value = _yf_frame(
        {
            t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
            for t in ["AAPL", BENCHMARK]
        },
        n,
    )

    try:
        main(["AAPL", "--plot"])  # must not raise
        assert mock_show.called, "the chart was never displayed"
        figure = plt.gcf()
        assert len(figure.axes) == 2, "expected a Sharpe axis and a Sortino axis"
        titles = [ax.get_title() for ax in figure.axes]
        assert any("Sharpe" in t for t in titles)
        assert any("Sortino" in t for t in titles)
    finally:
        plt.close("all")

    assert "Highest Sharpe ratio" in capsys.readouterr().out


@patch("keep_rollin.cli.plt.show")
@patch("keep_rollin.data.yf.download")
def test_no_charts_without_the_flag(mock_dl, mock_show):
    n = 300
    rng = np.random.default_rng(7)
    mock_dl.return_value = _yf_frame(
        {
            t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
            for t in ["AAPL", BENCHMARK]
        },
        n,
    )

    main(["AAPL"])

    assert not mock_show.called
