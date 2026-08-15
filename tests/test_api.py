from __future__ import annotations

import datetime
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from keep_rollin.api import app, clear_cache
from keep_rollin.data import default_date_range

client = TestClient(app)

TICKERS = ["MSFT", "NVDA"]
BENCHMARK = "^GSPC"


@pytest.fixture(autouse=True)
def _isolate_cache():
    """The price cache is process-wide; leaking it across tests hides bugs."""
    clear_cache()
    yield
    clear_cache()


def _prices(tickers: list[str], n: int = 300) -> pd.DataFrame:
    """Deterministic price history shaped like yf.download output."""
    rng = np.random.default_rng(0)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    data = {t: 100.0 * np.cumprod(1 + rng.normal(0.0005, 0.02, n)) for t in tickers}
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_arrays([["Close"] * len(tickers), tickers])
    return df


def _params(**overrides) -> dict:
    params = {
        "tickers": TICKERS,
        "start": "2020-01-01",
        "end": "2021-01-01",
    }
    params.update(overrides)
    return params


def test_health_reports_ok_and_finds_snapshot():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "fallback_available": True}


@patch("keep_rollin.data.yf.download")
def test_metrics_returns_one_entry_per_ticker(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    response = client.get("/metrics", params=_params())
    assert response.status_code == 200
    body = response.json()
    assert [a["ticker"] for a in body["assets"]] == TICKERS
    assert body["used_fallback"] is False
    assert body["rolling_window"] == 63
    assert body["observations"] > 0


@patch("keep_rollin.data.yf.download")
def test_metrics_match_the_shared_summary(mock_dl):
    """The API must report exactly what the CLI computes, not a re-derivation."""
    from keep_rollin.data import fetch_prices
    from keep_rollin.metrics import summarise

    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    stocks, bm = fetch_prices(TICKERS, BENCHMARK, "2020-01-01", "2021-01-01")
    expected = summarise(stocks, bm, window=63)

    body = client.get("/metrics", params=_params()).json()
    for asset in body["assets"]:
        row = expected.loc[asset["ticker"]]
        for column in expected.columns:
            assert asset[column] == pytest.approx(row[column])


@patch("keep_rollin.data.yf.download")
def test_best_sharpe_is_the_highest_scoring_ticker(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    body = client.get("/metrics", params=_params()).json()
    ranked = max(body["assets"], key=lambda a: a["sharpe"])
    assert body["best_sharpe"] == ranked["ticker"]


@patch("keep_rollin.data.yf.download")
def test_rolling_window_is_honoured(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    body = client.get("/metrics", params=_params(rolling_window=21)).json()
    assert body["rolling_window"] == 21


@patch("keep_rollin.data.yf.download")
def test_tickers_are_normalised_and_deduplicated(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    body = client.get(
        "/metrics", params=_params(tickers=["msft", " MSFT ", "nvda"])
    ).json()
    assert [a["ticker"] for a in body["assets"]] == TICKERS


@patch("keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited"))
def test_upstream_failure_serves_snapshot_and_flags_it(mock_dl):
    response = client.get(
        "/metrics", params=_params(start="2022-01-01", end="2023-01-01")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["used_fallback"] is True
    assert [a["ticker"] for a in body["assets"]] == TICKERS


@patch("keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited"))
def test_unservable_symbols_return_503(mock_dl):
    response = client.get("/metrics", params=_params(tickers=["NOPE"]))
    assert response.status_code == 503
    assert "NOPE" in response.json()["detail"]


@patch("keep_rollin.data.yf.download")
def test_metrics_works_with_no_parameters_at_all(mock_dl):
    """GET /metrics bare must return the default tickers over the default window."""
    from keep_rollin.data import DEFAULT_TICKERS, default_date_range

    mock_dl.return_value = _prices(list(DEFAULT_TICKERS) + [BENCHMARK])
    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.json()
    assert [a["ticker"] for a in body["assets"]] == list(DEFAULT_TICKERS)

    expected_start, expected_end = default_date_range()
    assert body["start"] == str(expected_start)
    assert body["end"] == str(expected_end)
    assert body["benchmark"] == "^GSPC"


@patch("keep_rollin.data.yf.download")
def test_default_window_spans_five_years(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    body = client.get("/metrics").json()
    start = datetime.date.fromisoformat(body["start"])
    end = datetime.date.fromisoformat(body["end"])
    assert end.year - start.year == 5


@patch("keep_rollin.data.yf.download")
def test_dates_default_independently(mock_dl):
    """Supplying only one date still yields a usable window."""
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])

    only_start = client.get("/metrics", params={"start": "2024-01-01"}).json()
    assert only_start["start"] == "2024-01-01"
    assert only_start["end"] == str(default_date_range()[1])

    only_end = client.get("/metrics", params={"end": "2024-01-01"}).json()
    assert only_end["end"] == "2024-01-01"
    assert only_end["start"] == str(default_date_range()[0])


@patch("keep_rollin.data.yf.download")
def test_explicit_parameters_still_win(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    body = client.get("/metrics", params=_params(tickers=["MSFT"])).json()
    assert [a["ticker"] for a in body["assets"]] == ["MSFT"]
    assert body["start"] == "2020-01-01"
    assert body["end"] == "2021-01-01"


def test_end_before_start_is_rejected():
    response = client.get(
        "/metrics", params=_params(start="2021-01-01", end="2020-01-01")
    )
    assert response.status_code == 422


def test_blank_tickers_are_rejected():
    """Omitting tickers falls back to the defaults, but asking for nothing is an error."""
    response = client.get("/metrics", params=_params(tickers=["", "  "]))
    assert response.status_code == 422


def test_out_of_range_window_is_rejected():
    response = client.get("/metrics", params=_params(rolling_window=1))
    assert response.status_code == 422


def test_malformed_date_is_rejected():
    response = client.get("/metrics", params=_params(start="not-a-date"))
    assert response.status_code == 422


@patch("keep_rollin.data.yf.download")
def test_repeat_request_is_served_from_cache(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])

    first = client.get("/metrics", params=_params())
    second = client.get("/metrics", params=_params())

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert mock_dl.call_count == 1, "cache hit must not re-fetch upstream"
    assert first.json() == second.json()


@patch("keep_rollin.data.yf.download")
def test_cache_is_keyed_on_the_fetch_not_the_window(mock_dl):
    """Changing only rolling_window must reuse the cached prices."""
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])

    client.get("/metrics", params=_params(rolling_window=63))
    other = client.get("/metrics", params=_params(rolling_window=21))

    assert mock_dl.call_count == 1
    assert other.headers["X-Cache"] == "HIT"
    assert other.json()["rolling_window"] == 21


@patch("keep_rollin.data.yf.download")
def test_different_parameters_are_cached_separately(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])

    client.get("/metrics", params=_params())
    client.get("/metrics", params=_params(start="2020-02-01"))

    assert mock_dl.call_count == 2


@patch("keep_rollin.data.yf.download")
def test_clearing_the_cache_forces_a_refetch(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])

    client.get("/metrics", params=_params())
    clear_cache()
    again = client.get("/metrics", params=_params())

    assert mock_dl.call_count == 2
    assert again.headers["X-Cache"] == "MISS"


@patch("keep_rollin.data.yf.download", side_effect=RuntimeError("rate limited"))
def test_fallback_results_expire_sooner_than_live_ones(mock_dl):
    """A cached snapshot must not pin stale data once upstream recovers."""
    from keep_rollin import api

    assert api.FALLBACK_CACHE_TTL_SECONDS < api.CACHE_TTL_SECONDS

    client.get("/metrics", params=_params(start="2022-01-01", end="2023-01-01"))
    key = (tuple(TICKERS), BENCHMARK, "2022-01-01", "2023-01-01")
    expires_at, _ = api._cache[key]
    remaining = expires_at - time.monotonic()
    assert remaining <= api.FALLBACK_CACHE_TTL_SECONDS


@patch("keep_rollin.data.yf.download")
def test_expired_entries_are_refetched(mock_dl):
    from keep_rollin import api

    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    client.get("/metrics", params=_params())

    # Expire the entry in place rather than sleeping out the real TTL.
    key = (tuple(TICKERS), BENCHMARK, "2020-01-01", "2021-01-01")
    _, payload = api._cache[key]
    api._cache[key] = (time.monotonic() - 1, payload)

    refreshed = client.get("/metrics", params=_params())
    assert refreshed.headers["X-Cache"] == "MISS"
    assert mock_dl.call_count == 2


@patch("keep_rollin.data.yf.download")
def test_cache_evicts_oldest_entries_past_the_limit(mock_dl):
    from keep_rollin import api

    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])

    # Each distinct start date is a distinct cache key.
    first_start = datetime.date(2019, 1, 1)
    for offset in range(api.CACHE_MAX_ENTRIES + 5):
        start = first_start + datetime.timedelta(days=offset)
        client.get("/metrics", params=_params(start=str(start), end="2021-01-01"))

    assert len(api._cache) == api.CACHE_MAX_ENTRIES
    # The earliest key is the one that should have been evicted.
    evicted = (tuple(TICKERS), BENCHMARK, str(first_start), "2021-01-01")
    assert evicted not in api._cache


@patch("keep_rollin.data.yf.download")
def test_fetch_uses_an_explicit_timeout(mock_dl):
    from keep_rollin.data import FETCH_TIMEOUT_SECONDS

    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    client.get("/metrics", params=_params())
    assert mock_dl.call_args.kwargs["timeout"] == FETCH_TIMEOUT_SECONDS


@patch("keep_rollin.data.yf.download")
def test_undefined_metrics_return_a_note_not_an_error(mock_dl):
    """A flat series leaves every metric undefined; that is data, not a failure."""
    n = 60
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    frame = pd.DataFrame(
        {"FLAT": np.full(n, 100.0), BENCHMARK: np.full(n, 100.0)}, index=dates
    )
    frame.columns = pd.MultiIndex.from_arrays([["Close"] * 2, ["FLAT", BENCHMARK]])
    mock_dl.return_value = frame

    response = client.get("/metrics", params=_params(tickers=["FLAT"]))
    assert response.status_code == 200

    body = response.json()
    assert body["best_sharpe"] is None
    assert body["note"] is not None
    assert "flat" in body["note"]
    assert body["assets"][0]["sharpe"] is None


@patch("keep_rollin.data.yf.download")
def test_no_note_when_ranking_succeeds(mock_dl):
    mock_dl.return_value = _prices(TICKERS + [BENCHMARK])
    body = client.get("/metrics", params=_params()).json()
    assert body["best_sharpe"] is not None
    assert body["note"] is None


@patch("keep_rollin.data.yf.download")
def test_non_finite_metrics_serialise_as_null(mock_dl):
    """Sortino is infinite without downside returns; JSON cannot hold inf."""
    n = 300
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    # Asset rises every day, benchmark is flat -> excess returns never negative.
    frame = pd.DataFrame(
        {
            "MSFT": 100.0 * np.cumprod(np.full(n, 1.01)),
            BENCHMARK: np.full(n, 100.0),
        },
        index=dates,
    )
    frame.columns = pd.MultiIndex.from_arrays([["Close"] * 2, ["MSFT", BENCHMARK]])
    mock_dl.return_value = frame

    response = client.get("/metrics", params=_params(tickers=["MSFT"]))
    assert response.status_code == 200
    # Valid JSON with no bare NaN/Infinity tokens.
    assert b"Infinity" not in response.content
    assert b"NaN" not in response.content
    assert response.json()["assets"][0]["sortino"] is None
