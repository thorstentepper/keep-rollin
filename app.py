from __future__ import annotations

import datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from keep_rollin.data import fetch_prices
from keep_rollin.metrics import (
    daily_returns,
    excess_returns,
    max_drawdown,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    sharpe_ratio,
    sortino_ratio,
)

st.set_page_config(page_title="keep-rollin", layout="wide")
st.title("keep-rollin")
st.caption("Annualised risk/return metrics for multi-asset portfolios")

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Parameters")
    tickers_raw = st.text_input("Tickers (comma-separated)", "AMZN, META")
    benchmark = st.text_input("Benchmark", "^GSPC")
    today = datetime.date.today()
    start = st.date_input("Start date", today.replace(year=today.year - 5))
    end = st.date_input("End date", today)
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


@st.cache_data
def load(
    tickers: tuple[str, ...],
    benchmark: str,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.Series]:
    return fetch_prices(tickers, benchmark, start, end)


with st.spinner("Fetching data from Yahoo Finance…"):
    try:
        stock_prices, benchmark_prices = load(
            tuple(tickers), benchmark, str(start), str(end)
        )
    except Exception as exc:
        st.error(f"Failed to fetch data: {exc}")
        st.stop()

if stock_prices.empty:
    st.error("No data returned — check your tickers and date range.")
    st.stop()

# ── Calculations ──────────────────────────────────────────────────────────────

stock_ret = daily_returns(stock_prices)
bench_ret = daily_returns(benchmark_prices)
exc = excess_returns(stock_ret, bench_ret)
rolling_sharpe = rolling_sharpe_ratio(exc, window=window)
rolling_sortino = rolling_sortino_ratio(exc, window=window)

results = pd.DataFrame(
    {
        "Sharpe (ann.)": sharpe_ratio(exc),
        "Sortino (ann.)": sortino_ratio(exc),
        "Max Drawdown": max_drawdown(stock_prices),
        f"Avg Rolling Sharpe ({window}d)": rolling_sharpe.mean(),
        f"Avg Rolling Sortino ({window}d)": rolling_sortino.mean(),
    }
).round(2)

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
