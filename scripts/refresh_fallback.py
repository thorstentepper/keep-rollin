"""Regenerate the bundled fallback price snapshot.

The Streamlit app and CLI fetch prices live from Yahoo Finance. When that
fails — rate limiting, an upstream API change, or no network at all — the
shipped parquet snapshot written by this script lets the app still render a
complete result instead of erroring out.

Run from the repo root whenever the snapshot should be brought up to date:

    uv run python scripts/refresh_fallback.py

The snapshot holds the asset columns and the benchmark column side by side on
a shared index; the benchmark's name is recorded in the parquet metadata so
readers do not have to hardcode it.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from keep_rollin.data import (
    DEFAULT_BENCHMARK,
    DEFAULT_TICKERS,
    default_date_range,
    fetch_prices,
)

# A 252-day rolling window needs at least that many rows before it yields a
# single value, so a snapshot shorter than this would render empty charts.
MIN_ROWS = 252

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT / "src" / "keep_rollin" / "resources" / "fallback_prices.parquet"
)


def _build_parser() -> argparse.ArgumentParser:
    start, end = default_date_range()
    parser = argparse.ArgumentParser(
        description="Regenerate the bundled fallback price snapshot.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        default=list(DEFAULT_TICKERS),
        help="Yahoo Finance ticker symbols to snapshot",
    )
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help="Benchmark ticker symbol",
    )
    parser.add_argument(
        "--start",
        default=str(start),
        help="Start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        default=str(end),
        help="End date YYYY-MM-DD",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination parquet file",
    )
    return parser


def build_snapshot(
    tickers: list[str],
    benchmark: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Fetch prices and align assets and benchmark onto one index.

    ``fetch_prices`` drops missing values from the assets and the benchmark
    independently, so the two can end up with different indices. Joining on
    the intersection keeps every row complete, which is what the metrics
    functions expect.
    """
    stock_prices, benchmark_prices = fetch_prices(tickers, benchmark, start, end)
    frame = stock_prices.join(benchmark_prices.rename(benchmark), how="inner").dropna()
    frame.index.name = "Date"
    return frame


def validate(frame: pd.DataFrame, tickers: list[str], benchmark: str) -> None:
    """Refuse to overwrite a good snapshot with an unusable one."""
    missing = [c for c in [*tickers, benchmark] if c not in frame.columns]
    if missing:
        raise ValueError(f"missing columns in fetched data: {missing}")
    if len(frame) < MIN_ROWS:
        raise ValueError(
            f"only {len(frame)} rows fetched, need at least {MIN_ROWS} "
            "to support a 252-day rolling window"
        )
    if not frame.notna().all().all():
        raise ValueError("fetched data still contains missing values after join")


def write_snapshot(
    frame: pd.DataFrame,
    output: Path,
    tickers: list[str],
    benchmark: str,
) -> None:
    """Write the parquet file, recording provenance in the schema metadata."""
    table = pa.Table.from_pandas(frame)
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata = {
        **(table.schema.metadata or {}),
        b"benchmark": benchmark.encode(),
        b"tickers": ",".join(tickers).encode(),
        b"start": str(frame.index.min().date()).encode(),
        b"end": str(frame.index.max().date()).encode(),
        b"generated_utc": generated.encode(),
    }
    table = table.replace_schema_metadata(metadata)

    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output, compression="snappy")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    tickers = [t.strip().upper() for t in args.tickers if t.strip()]

    print(
        f"Fetching {tickers} vs {args.benchmark} "
        f"({args.start} → {args.end}) for the fallback snapshot..."
    )
    try:
        frame = build_snapshot(tickers, args.benchmark, args.start, args.end)
        validate(frame, tickers, args.benchmark)
    except Exception as exc:
        # The existing snapshot is the safety net — leave it untouched.
        print(f"Refresh failed, snapshot left unchanged: {exc}", file=sys.stderr)
        return 1

    write_snapshot(frame, args.output, tickers, args.benchmark)

    size_kb = args.output.stat().st_size / 1024
    print(
        f"Wrote {args.output.relative_to(REPO_ROOT)} — "
        f"{len(frame)} rows × {len(frame.columns)} columns, "
        f"{frame.index.min().date()} → {frame.index.max().date()} ({size_kb:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
