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
