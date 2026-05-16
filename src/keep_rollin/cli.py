from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import pandas as pd

from keep_rollin.data import fetch_prices
from keep_rollin.metrics import (
    daily_returns,
    excess_returns,
    max_drawdown,
    rolling_sharpe_ratio,
    sharpe_ratio,
    sortino_ratio,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute annualised risk/return metrics for one or more tickers.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("tickers", nargs="+", help="Yahoo Finance ticker symbols")
    parser.add_argument(
        "--benchmark",
        default="^GSPC",
        help="Benchmark ticker symbol",
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--rolling-window",
        type=int,
        default=63,
        metavar="DAYS",
        help="Rolling Sharpe window in trading days (≈ 1 quarter)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Show a rolling Sharpe ratio chart",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    print(
        f"Fetching data for {args.tickers} vs {args.benchmark} "
        f"({args.start} → {args.end})..."
    )
    stock_prices, benchmark_prices = fetch_prices(
        args.tickers, args.benchmark, args.start, args.end
    )

    stock_ret = daily_returns(stock_prices)
    bench_ret = daily_returns(benchmark_prices)
    exc = excess_returns(stock_ret, bench_ret)

    rolling = rolling_sharpe_ratio(exc, window=args.rolling_window)
    results = pd.DataFrame(
        {
            "Sharpe (ann.)": sharpe_ratio(exc),
            "Sortino (ann.)": sortino_ratio(exc),
            "Max Drawdown": max_drawdown(stock_prices),
            f"Avg Rolling Sharpe ({args.rolling_window}d)": rolling.mean(),
        }
    ).round(2)

    print("\n--- Results ---")
    print(results.to_string())
    best = results["Sharpe (ann.)"].idxmax()
    print(f"\nHighest Sharpe ratio: {best} ({results.loc[best, 'Sharpe (ann.)']:.2f})")

    if args.plot:
        ax = rolling.plot(
            title=f"Rolling Sharpe Ratio ({args.rolling_window}-day window)",
            figsize=(10, 4),
        )
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_ylabel("Sharpe Ratio (annualised)")
        ax.set_xlabel("")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
