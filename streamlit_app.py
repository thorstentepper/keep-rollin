from __future__ import annotations

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
    daily_returns,
    excess_returns,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    summarise,
)

st.set_page_config(page_title="keep-rollin", layout="wide")
st.title("keep-rollin")
st.caption("Annualised risk/return metrics for multi-asset portfolios")

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
        max_value=252,
        value=63,
        help="21 ≈ 1 month  ·  63 ≈ 1 quarter  ·  252 ≈ 1 year",
    )
    run = st.button("Analyse", type="primary", width="stretch")

# ── Guard clauses ─────────────────────────────────────────────────────────────

if not run:
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


# The TTL matters: without it a fallback result would be cached for the life of
# the process, pinning the offline snapshot long after Yahoo Finance recovered.
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
    st.warning(
        f"Yahoo Finance is unavailable — showing the bundled offline snapshot "
        f"({stock_prices.index.min():%Y-%m-%d} → {stock_prices.index.max():%Y-%m-%d}). "
        "These figures are not live."
    )

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

best = results["Sharpe (ann.)"].idxmax()

st.subheader("Summary")
st.dataframe(results, width="stretch")
st.caption(f"Highest Sharpe: **{best}** ({results.loc[best, 'Sharpe (ann.)']:.2f})")

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
