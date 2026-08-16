"""Tests for the Streamlit dashboard.

Widgets are looked up by label rather than by index on purpose: adding the
"Retry live data" button once shifted every positional index, which fails in a
confusing way. Every test patches ``yf.download`` — an unpatched test would
reach the network and flake in CI.

Requires the ``app`` extra (``uv sync --extra app``).
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = "streamlit_app.py"
TIMEOUT = 60

TICKERS_LABEL = "Tickers (comma-separated)"


@pytest.fixture(autouse=True)
def _isolate_cache():
    """st.cache_data is process-wide; leaking it between tests hides bugs."""
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _yf_frame(tickers: list[str], n: int = 400) -> pd.DataFrame:
    """A yf.download-shaped frame with a plausible upward drift."""
    dates = pd.date_range("2021-08-16", periods=n, freq="B")
    rng = np.random.default_rng(0)
    columns = {t: 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n)) for t in tickers}
    frame = pd.DataFrame(columns, index=dates)
    frame.columns = pd.MultiIndex.from_arrays([["Close"] * len(columns), list(columns)])
    return frame


def _flat_frame(tickers: list[str], n: int = 400) -> pd.DataFrame:
    """Prices that never move, leaving every metric undefined."""
    dates = pd.date_range("2021-08-16", periods=n, freq="B")
    frame = pd.DataFrame({t: np.full(n, 100.0) for t in tickers}, index=dates)
    frame.columns = pd.MultiIndex.from_arrays([["Close"] * len(tickers), tickers])
    return frame


def _live(tickers, *_args, **_kwargs) -> pd.DataFrame:
    return _yf_frame(list(tickers))


def _widget(elements, label):
    for element in elements:
        if element.label == label:
            return element
    raise AssertionError(
        f"no widget labelled {label!r} in {[e.label for e in elements]}"
    )


def _analyse(tickers: str | None = None) -> AppTest:
    """Open the app, optionally set tickers, and click Analyse."""
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    if tickers is not None:
        _widget(at.sidebar.text_input, TICKERS_LABEL).set_value(tickers).run()
    return _widget(at.button, "Analyse").click().run()


def _has_fallback_banner(at: AppTest) -> bool:
    return any("offline snapshot" in w.value for w in at.warning)


# ── Rendering ────────────────────────────────────────────────────────────────


def test_intro_shown_before_analysing():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.run()
    assert at.info, "expected the configure-and-click prompt"
    assert not at.dataframe, "no results should render before Analyse"


def test_analyse_renders_summary_and_both_leaders():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = _analyse()

    assert not at.exception
    assert len(at.dataframe) == 1
    captions = " ".join(c.value for c in at.caption)
    assert "Highest Sharpe" in captions
    assert "Highest Sortino" in captions


def test_title_and_strapline():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.run()
    assert at.title[0].value == "Keep Rollin'"
    assert "rolling windows" in at.caption[0].value


# ── Validation ───────────────────────────────────────────────────────────────


def test_blank_tickers_are_rejected():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = _analyse("   ")
    assert any("at least one ticker" in e.value for e in at.error)
    assert not at.dataframe


# ── Offline fallback ─────────────────────────────────────────────────────────


def test_upstream_failure_shows_the_fallback_banner():
    with patch(
        "keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited")
    ):
        at = _analyse()

    assert not at.exception
    assert _has_fallback_banner(at)
    assert len(at.dataframe) == 1, "the snapshot should still render a table"


def test_a_fallback_is_not_cached_for_later_requests():
    """Regression: one failed fetch used to pin the snapshot for the whole TTL.

    A different ticker set would fetch live data quite happily, while the
    original one kept serving the snapshot until the cache expired.
    """
    calls = {"n": 0}

    def fail_once(tickers, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("cold start")
        return _yf_frame(list(tickers))

    with patch("keep_rollin.data.yf.download", side_effect=fail_once):
        first = _analyse()
        other = _analyse("AMZN, META")
        again = _analyse("MSFT, NVDA")

    assert _has_fallback_banner(first)
    assert not _has_fallback_banner(other)
    assert not _has_fallback_banner(again), "the failed lookup was retried, not cached"


def test_retry_button_recovers_once_upstream_returns():
    failing = {"yes": True}

    def flaky(tickers, *args, **kwargs):
        if failing["yes"]:
            raise RuntimeError("rate limited")
        return _yf_frame(list(tickers))

    with patch("keep_rollin.data.yf.download", side_effect=flaky):
        at = _analyse()
        assert _has_fallback_banner(at)

        failing["yes"] = False
        at = _widget(at.button, "Retry live data").click().run()

    assert not _has_fallback_banner(at)
    assert len(at.dataframe) == 1
    assert not at.error


def test_no_retry_button_when_data_is_live():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = _analyse()
    assert [b.label for b in at.button] == ["Analyse"]


def test_live_results_are_cached():
    calls = {"n": 0}

    def counting(tickers, *args, **kwargs):
        calls["n"] += 1
        return _yf_frame(list(tickers))

    with patch("keep_rollin.data.yf.download", side_effect=counting):
        for _ in range(3):
            _analyse()

    assert calls["n"] == 1, "identical requests should hit the cache"


# ── Undefined metrics ────────────────────────────────────────────────────────


def test_flat_prices_explain_instead_of_crashing():
    """Regression: an all-undefined column used to raise straight out of idxmax."""
    with patch(
        "keep_rollin.data.yf.download",
        side_effect=lambda tickers, *a, **k: _flat_frame(list(tickers)),
    ):
        at = _analyse("FLAT")

    assert not at.exception
    assert any("No ranked result" in w.value for w in at.warning)
    captions = " ".join(c.value for c in at.caption)
    assert "Highest Sharpe" not in captions


# ── Stated conventions ───────────────────────────────────────────────────────


def test_conventions_are_stated_before_analysing():
    """The benchmark-relative basis governs the numbers, so say it up front."""
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.run()

    captions = " ".join(c.value for c in at.caption)
    assert "not a risk-free rate" in captions
    assert "252" in captions
    assert "inclusive" in captions


def test_results_name_the_benchmark_actually_used():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = _analyse()

    basis = [c.value for c in at.caption if "Excess returns over" in c.value]
    assert basis, "the summary should state what the metrics are measured against"
    assert "^GSPC" in basis[0]


def test_basis_line_follows_a_changed_benchmark():
    with patch("keep_rollin.data.yf.download", side_effect=_live):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.run()
        _widget(at.sidebar.text_input, "Benchmark").set_value("^IXIC").run()
        at = _widget(at.button, "Analyse").click().run()

    basis = [c.value for c in at.caption if "Excess returns over" in c.value][0]
    assert "^IXIC" in basis and "^GSPC" not in basis


def test_basis_line_reports_the_data_actually_used_not_the_request():
    """Under the fallback it must agree with the banner, not the requested range."""
    with patch(
        "keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited")
    ):
        at = _analyse()

    banner = [w.value for w in at.warning if "offline snapshot" in w.value][0]
    basis = [c.value for c in at.caption if "Excess returns over" in c.value][0]
    for date in ("2021-08-16", "2026-08-14"):
        assert date in banner and date in basis
