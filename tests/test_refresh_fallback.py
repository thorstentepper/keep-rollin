"""Tests for scripts/refresh_fallback.py.

The script maintains the offline snapshot the whole fallback path depends on,
so its most important behaviour is refusing to overwrite a good snapshot with
a bad fetch. It lives outside the package, so it is loaded by path.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "refresh_fallback.py"
_spec = importlib.util.spec_from_file_location("refresh_fallback", _PATH)
refresh = importlib.util.module_from_spec(_spec)
sys.modules["refresh_fallback"] = refresh
_spec.loader.exec_module(refresh)

TICKERS = ["MSFT", "NVDA"]
BENCHMARK = "^GSPC"


def _yf_frame(n: int, tickers=None) -> pd.DataFrame:
    """A yf.download-shaped response with `n` business days."""
    tickers = tickers or [*TICKERS, BENCHMARK]
    dates = pd.date_range("2021-08-16", periods=n, freq="B")
    rng = np.random.default_rng(0)
    cols = {t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n)) for t in tickers}
    frame = pd.DataFrame(cols, index=dates)
    frame.columns = pd.MultiIndex.from_arrays([["Close"] * len(cols), list(cols)])
    return frame


# ── Building ─────────────────────────────────────────────────────────────────


@patch("keep_rollin.data.yf.download")
def test_snapshot_puts_assets_and_benchmark_on_one_index(mock_dl):
    mock_dl.return_value = _yf_frame(300)
    frame = refresh.build_snapshot(TICKERS, BENCHMARK, "2021-08-16", "2022-10-14")

    assert list(frame.columns) == [*TICKERS, BENCHMARK]
    assert frame.index.name == "Date"
    assert not frame.isna().any().any(), "every row must be complete after the join"


# ── Validation ───────────────────────────────────────────────────────────────


def _good_frame(n: int = 300) -> pd.DataFrame:
    dates = pd.date_range("2021-08-16", periods=n, freq="B")
    return pd.DataFrame(
        {t: np.arange(100.0, 100.0 + n) for t in [*TICKERS, BENCHMARK]}, index=dates
    )


def test_validate_accepts_a_usable_snapshot():
    refresh.validate(_good_frame(), TICKERS, BENCHMARK)  # must not raise


def test_validate_rejects_a_short_snapshot():
    """Too few rows and the 252-day rolling window yields nothing."""
    with pytest.raises(ValueError, match="need at least"):
        refresh.validate(_good_frame(refresh.MIN_ROWS - 1), TICKERS, BENCHMARK)


def test_validate_rejects_missing_columns():
    frame = _good_frame().drop(columns=[BENCHMARK])
    with pytest.raises(ValueError, match="missing columns"):
        refresh.validate(frame, TICKERS, BENCHMARK)


def test_validate_rejects_residual_gaps():
    frame = _good_frame()
    frame.iloc[5, 0] = np.nan
    with pytest.raises(ValueError, match="missing values"):
        refresh.validate(frame, TICKERS, BENCHMARK)


# ── Writing ──────────────────────────────────────────────────────────────────


def test_written_snapshot_records_its_provenance(tmp_path):
    out = tmp_path / "snap.parquet"
    refresh.write_snapshot(_good_frame(), out, TICKERS, BENCHMARK)

    metadata = pq.read_schema(out).metadata
    assert metadata[b"benchmark"].decode() == BENCHMARK
    assert metadata[b"tickers"].decode() == ",".join(TICKERS)
    assert b"generated_utc" in metadata

    reread = pd.read_parquet(out)
    assert list(reread.columns) == [*TICKERS, BENCHMARK]


# ── End to end ───────────────────────────────────────────────────────────────


@patch("keep_rollin.data.yf.download")
def test_main_writes_a_snapshot_and_reports_success(mock_dl, tmp_path):
    mock_dl.return_value = _yf_frame(300)
    out = tmp_path / "snap.parquet"

    code = refresh.main([*TICKERS, "--benchmark", BENCHMARK, "--output", str(out)])

    assert code == 0
    assert out.exists()
    assert len(pd.read_parquet(out)) >= refresh.MIN_ROWS


@patch("keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited"))
def test_a_failed_fetch_leaves_the_existing_snapshot_untouched(mock_dl, tmp_path):
    """The existing snapshot is the safety net; a bad run must not destroy it."""
    out = tmp_path / "snap.parquet"
    refresh.write_snapshot(_good_frame(), out, TICKERS, BENCHMARK)
    before = out.read_bytes()

    code = refresh.main([*TICKERS, "--output", str(out)])

    assert code == 1, "a failed fetch must report failure"
    assert out.read_bytes() == before, "the good snapshot was overwritten"


@patch("keep_rollin.data.yf.download")
def test_a_short_fetch_also_leaves_the_snapshot_untouched(mock_dl, tmp_path):
    mock_dl.return_value = _yf_frame(10)  # well below MIN_ROWS
    out = tmp_path / "snap.parquet"
    refresh.write_snapshot(_good_frame(), out, TICKERS, BENCHMARK)
    before = out.read_bytes()

    assert refresh.main([*TICKERS, "--output", str(out)]) == 1
    assert out.read_bytes() == before
