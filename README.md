# keep-rollin

## Description

Computes annualised risk/return metrics for one or more assets against a configurable benchmark:

- **Sharpe ratio** — excess return per unit of total volatility
- **Sortino ratio** — excess return per unit of downside volatility (doesn't penalise upside)
- **Max drawdown** — largest peak-to-trough decline over the period
- **Rolling Sharpe ratio** — Sharpe ratio computed over a sliding window (default: 63 trading days ≈ 1 quarter)
- **Rolling Sortino ratio** — same, but penalising only downside volatility within each window

Data is fetched live from Yahoo Finance, so any ticker and date range can be analysed without managing local CSV files.

Originally completed as a DataCamp project in January 2022; the notebook is preserved in `notebooks/`.


## Installation

```bash
pip install -e ".[dev]"
```


## Usage

```bash
sharpe AMZN META --benchmark ^GSPC --start 2016-01-01 --end 2016-12-31
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--benchmark` | `^GSPC` | Yahoo Finance symbol for the benchmark |
| `--start` | required | Start date `YYYY-MM-DD` |
| `--end` | required | End date `YYYY-MM-DD` |
| `--rolling-window` | `63` | Rolling Sharpe window in trading days |
| `--plot` | off | Display the rolling Sharpe ratio chart |


## Running tests

```bash
pytest
# with coverage
pytest --cov=keep_rollin
```


## Project structure

```
src/keep_rollin/
    data.py      — fetch adjusted close prices from Yahoo Finance
    metrics.py   — Sharpe, Sortino, max drawdown, rolling Sharpe, rolling Sortino
    cli.py       — command-line entry point
tests/
    test_data.py
    test_metrics.py
notebooks/
    sharpe_ratio.ipynb   — original DataCamp submission
pyproject.toml
```


## Credits

Original project tasks by Stefan Jansen for DataCamp.

The data used in `notebooks/sharpe_ratio.ipynb` comes from two DataCamp CSV files covering Amazon and Facebook vs. the S&P 500 for the full year 2016.
