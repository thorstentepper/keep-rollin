# Keep Rollin'

[![CI](https://github.com/thorstentepper/keep-rollin/actions/workflows/ci.yml/badge.svg)](https://github.com/thorstentepper/keep-rollin/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/thorstentepper/keep-rollin/branch/main/graph/badge.svg)](https://codecov.io/gh/thorstentepper/keep-rollin)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Description

Computes annualised risk/return metrics for one or more assets against a configurable benchmark:

- **Sharpe ratio** — excess return per unit of total volatility
- **Sortino ratio** — excess return per unit of downside volatility (doesn't penalise upside)
- **Max drawdown** — largest peak-to-trough decline over the period
- **Rolling Sharpe ratio** — Sharpe ratio computed over a sliding window (default: 63 trading days ≈ 1 quarter)
- **Rolling Sortino ratio** — same, but penalising only downside volatility within each window

Data is fetched live from Yahoo Finance, so any ticker and date range can be analysed without managing local CSV files.


## Installation

```bash
uv sync --all-extras          # library + CLI + dev tools + Streamlit
```

Or install a minimal set:

```bash
uv sync --extra dev           # library + CLI + dev tools only
```


## Usage

### Streamlit app

```bash
uv run streamlit run app.py
```

Opens an interactive dashboard in your browser: pick tickers, benchmark, date range, and rolling window from the sidebar and click **Analyse**.

#### Docker

```bash
docker build -t keep-rollin .
docker run --rm -p 8501:8501 keep-rollin
```

Then visit <http://localhost:8501>. The image runs as a non-root user and includes a healthcheck on Streamlit's `/_stcore/health` endpoint.

### CLI

```bash
rollin AMZN META --benchmark ^GSPC --start 2016-01-01 --end 2016-12-31
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--benchmark` | `^GSPC` | Yahoo Finance symbol for the benchmark |
| `--start` | required | Start date `YYYY-MM-DD` |
| `--end` | required | End date `YYYY-MM-DD` |
| `--rolling-window` | `63` | Rolling window in trading days (for both Sharpe and Sortino) |
| `--plot` | off | Display rolling Sharpe and Sortino ratio charts |


## Running tests

```bash
uv run pytest
# with coverage
uv run pytest --cov=keep_rollin
```


## Project structure

```
.github/workflows/ci.yml       — pytest on push/PR (Python 3.10 and 3.13)
Dockerfile                      — multi-stage build for Streamlit app
app.py                         — Streamlit dashboard
src/keep_rollin/
    data.py                    — fetch adjusted close prices from Yahoo Finance
    metrics.py                 — Sharpe, Sortino, max drawdown, rolling Sharpe, rolling Sortino
    cli.py                     — command-line entry point
tests/
    test_data.py
    test_metrics.py
notebooks/
    sharpe_ratio.ipynb         — original DataCamp submission
pyproject.toml
```


## Credits

The project began as a DataCamp exercise on the Sharpe Ratio (original tasks by Stefan Jansen, completed in January 2022). Everything in this repository — the package structure, Sortino and rolling-window metrics, CLI, Streamlit app, containerisation, and CI — was written from scratch.
