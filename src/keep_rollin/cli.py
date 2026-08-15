from __future__ import annotations

import argparse

import matplotlib.pyplot as plt

from keep_rollin.data import fetch_prices
from keep_rollin.metrics import (
    daily_returns,
    excess_returns,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    summarise,
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

    results = (
        summarise(stock_prices, benchmark_prices, window=args.rolling_window)
        .rename(
            columns={
                "sharpe": "Sharpe (ann.)",
                "sortino": "Sortino (ann.)",
                "max_drawdown": "Max Drawdown",
                "avg_rolling_sharpe": f"Avg Rolling Sharpe ({args.rolling_window}d)",
                "avg_rolling_sortino": f"Avg Rolling Sortino ({args.rolling_window}d)",
            }
        )
        .round(2)
    )

    print("\n--- Results ---")
    print(results.to_string())
    best = results["Sharpe (ann.)"].idxmax()
    print(f"\nHighest Sharpe ratio: {best} ({results.loc[best, 'Sharpe (ann.)']:.2f})")

    if args.plot:
        # The summary keeps only window averages, so recompute the series.
        exc = excess_returns(
            daily_returns(stock_prices), daily_returns(benchmark_prices)
        )
        rolling_sharpe = rolling_sharpe_ratio(exc, window=args.rolling_window)
        rolling_sortino = rolling_sortino_ratio(exc, window=args.rolling_window)

        fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        rolling_sharpe.plot(
            ax=axes[0], title=f"Rolling Sharpe ({args.rolling_window}-day window)"
        )
        axes[0].axhline(0, color="black", linewidth=0.8, linestyle="--")
        axes[0].set_ylabel("Sharpe (annualised)")
        rolling_sortino.plot(
            ax=axes[1], title=f"Rolling Sortino ({args.rolling_window}-day window)"
        )
        axes[1].axhline(0, color="black", linewidth=0.8, linestyle="--")
        axes[1].set_ylabel("Sortino (annualised)")
        axes[1].set_xlabel("")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
