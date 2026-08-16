from __future__ import annotations

import argparse

import matplotlib.pyplot as plt

from keep_rollin.data import (
    DEFAULT_BENCHMARK,
    DEFAULT_TICKERS,
    default_date_range,
    fetch_prices,
)
from keep_rollin.metrics import (
    DEFAULT_ROLLING_WINDOW,
    MAX_ROLLING_WINDOW,
    MIN_ROLLING_WINDOW,
    NO_LEADER_EXPLANATION,
    daily_returns,
    excess_returns,
    leader,
    rolling_sharpe_ratio,
    rolling_sortino_ratio,
    summarise,
)


def _rolling_window(value: str) -> int:
    """Validate the rolling window against the same bounds the API enforces."""
    try:
        window = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from None
    if not MIN_ROLLING_WINDOW <= window <= MAX_ROLLING_WINDOW:
        raise argparse.ArgumentTypeError(
            f"must be between {MIN_ROLLING_WINDOW} and {MAX_ROLLING_WINDOW} "
            f"trading days, got {window}"
        )
    return window


def _build_parser() -> argparse.ArgumentParser:
    # Every argument is optional, matching the HTTP API: both read their
    # defaults from keep_rollin.data, so the two cannot disagree about what a
    # bare invocation means.
    start, end = default_date_range()
    parser = argparse.ArgumentParser(
        description="Compute annualised risk/return metrics for one or more tickers.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        default=list(DEFAULT_TICKERS),
        help="Yahoo Finance ticker symbols",
    )
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help="Benchmark ticker symbol",
    )
    parser.add_argument("--start", default=str(start), help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=str(end), help="End date YYYY-MM-DD")
    parser.add_argument(
        "--rolling-window",
        type=_rolling_window,
        default=DEFAULT_ROLLING_WINDOW,
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
    """Run the command-line interface.

    Prints the metrics table for the requested tickers, then names the
    highest-Sharpe asset — or explains why no ranking was possible.

    Parameters
    ----------
    argv:
        Argument list to parse. Defaults to ``sys.argv[1:]``; passing an
        explicit list is what makes the CLI testable without a subprocess.

    Raises
    ------
    SystemExit
        If no usable ticker symbols remain after normalisation, or if
        argparse rejects an argument such as an out-of-range rolling window.
    """
    args = _build_parser().parse_args(argv)

    tickers = [t.strip().upper() for t in args.tickers if t.strip()]
    if not tickers:
        raise SystemExit("No usable ticker symbols given.")

    print(
        f"Fetching data for {tickers} vs {args.benchmark} "
        f"({args.start} → {args.end})..."
    )
    stock_prices, benchmark_prices = fetch_prices(
        tickers, args.benchmark, args.start, args.end
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

    best = leader(results["Sharpe (ann.)"])
    if best is None:
        print(f"\nNo ranked result: {NO_LEADER_EXPLANATION}.")
    else:
        print(
            f"\nHighest Sharpe ratio: {best} ({results.loc[best, 'Sharpe (ann.)']:.2f})"
        )

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
