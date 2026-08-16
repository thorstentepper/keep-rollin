from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from keep_rollin.data import (
    DEFAULT_BENCHMARK,
    DEFAULT_TICKERS,
    FallbackUnavailable,
    default_date_range,
    fetch_prices_with_fallback,
)
from keep_rollin.metrics import (
    DEFAULT_ROLLING_WINDOW,
    MAX_ROLLING_WINDOW,
    NO_LEADER_EXPLANATION,
    daily_returns,
    excess_returns,
    leader,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    summarise,
)

# Streamlit renders the script on a worker thread, and an interactive backend
# such as TkAgg crashes the interpreter when a figure is created off the main
# thread. Agg is headless and safe. Hosted deployments have no display and
# would pick Agg anyway; this protects local runs.
matplotlib.use("Agg")

st.set_page_config(page_title="Keep Rollin'", layout="wide")
st.title("Keep Rollin'")
st.caption(
    "Annualised risk/return metrics for multi-asset portfolios, "
    "including rolling windows."
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Parameters")
    tickers_raw = st.text_input("Tickers (comma-separated)", ", ".join(DEFAULT_TICKERS))
    benchmark = st.text_input("Benchmark", DEFAULT_BENCHMARK)
    default_start, default_end = default_date_range()
    start = st.date_input("Start date", default_start)
    end = st.date_input("End date", default_end)
    window = st.slider(
        "Rolling window (trading days)",
        min_value=21,
        max_value=MAX_ROLLING_WINDOW,
        value=DEFAULT_ROLLING_WINDOW,
        help="21 ≈ 1 month  ·  63 ≈ 1 quarter  ·  252 ≈ 1 year",
    )
    run = st.button("Analyse", type="primary", width="stretch")

# ── Guard clauses ─────────────────────────────────────────────────────────────

if run:
    st.session_state.analysed = True

# Tracked in session state rather than read straight off the button: the retry
# control below triggers a rerun in which "Analyse" is no longer pressed, and
# without this the app would fall back to the intro screen instead of
# recomputing.
if not st.session_state.get("analysed", False):
    st.info("Configure parameters in the sidebar and click **Analyse**.")
    st.stop()

tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
if not tickers:
    st.error("Enter at least one ticker.")
    st.stop()

if end <= start:
    st.error("End date must be after start date.")
    st.stop()

# ── Data fetching ─────────────────────────────────────────────────────────────


# Live prices are worth caching: daily closes do not change intraday, and this
# keeps repeat views off Yahoo Finance's rate limiter. Fallback results are
# evicted immediately after use (see below), so one failed fetch cannot pin the
# offline snapshot for the whole TTL.
@st.cache_data(ttl=900)
def load(
    tickers: tuple[str, ...],
    benchmark: str,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.Series, bool]:
    return fetch_prices_with_fallback(tickers, benchmark, start, end)


with st.spinner("Fetching data from Yahoo Finance…"):
    try:
        stock_prices, benchmark_prices, used_fallback = load(
            tuple(tickers), benchmark, str(start), str(end)
        )
    except FallbackUnavailable as exc:
        st.error(
            f"Yahoo Finance is unavailable and the bundled snapshot cannot "
            f"cover this request: {exc}"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Failed to fetch data: {exc}")
        st.stop()

if stock_prices.empty:
    st.error("No data returned — check your tickers and date range.")
    st.stop()

if used_fallback:
    # Drop this entry so the next run asks Yahoo Finance again. A single failed
    # fetch — a cold start, or a momentary rate limit — would otherwise keep
    # serving the snapshot for these exact inputs until the TTL expired, while
    # any other ticker combination fetched live data quite happily.
    load.clear(tuple(tickers), benchmark, str(start), str(end))

    st.warning(
        f"Yahoo Finance is unavailable — showing the bundled offline snapshot "
        f"({stock_prices.index.min():%Y-%m-%d} → {stock_prices.index.max():%Y-%m-%d}). "
        "These figures are not live."
    )
    if st.button("Retry live data"):
        load.clear()
        st.rerun()

# ── Calculations ──────────────────────────────────────────────────────────────

stock_ret = daily_returns(stock_prices)
bench_ret = daily_returns(benchmark_prices)
exc = excess_returns(stock_ret, bench_ret)
rolling_sharpe = rolling_sharpe_ratio(exc, window=window)
rolling_sortino = rolling_sortino_ratio(exc, window=window)

results = (
    summarise(stock_prices, benchmark_prices, window=window)
    .rename(
        columns={
            "sharpe": "Sharpe (ann.)",
            "sortino": "Sortino (ann.)",
            "max_drawdown": "Max Drawdown",
            "avg_rolling_sharpe": f"Avg Rolling Sharpe ({window}d)",
            "avg_rolling_sortino": f"Avg Rolling Sortino ({window}d)",
        }
    )
    .round(2)
)

# ── Results table ─────────────────────────────────────────────────────────────

best_sharpe = leader(results["Sharpe (ann.)"])
best_sortino = leader(results["Sortino (ann.)"])

st.subheader("Summary")
st.dataframe(results, width="stretch")

if best_sharpe is None and best_sortino is None:
    st.warning(f"No ranked result — {NO_LEADER_EXPLANATION}.")
else:
    if best_sharpe is not None:
        st.caption(
            f"Highest Sharpe: **{best_sharpe}** "
            f"({results.loc[best_sharpe, 'Sharpe (ann.)']:.2f})"
        )
    if best_sortino is not None:
        st.caption(
            f"Highest Sortino: **{best_sortino}** "
            f"({results.loc[best_sortino, 'Sortino (ann.)']:.2f})"
        )

# ── Rolling charts ────────────────────────────────────────────────────────────


def _plot_rolling(series: pd.DataFrame, ylabel: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 3))
    series.plot(ax=ax)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    ax.legend(loc="upper left")
    plt.tight_layout()
    return fig


st.subheader(f"Rolling Sharpe ratio — {window}-day window")
fig = _plot_rolling(rolling_sharpe, "Sharpe (annualised)")
st.pyplot(fig)
plt.close(fig)

st.subheader(f"Rolling Sortino ratio — {window}-day window")
fig = _plot_rolling(rolling_sortino, "Sortino (annualised)")
st.pyplot(fig)
plt.close(fig)
