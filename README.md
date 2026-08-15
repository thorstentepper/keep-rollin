# Keep Rollin'

[![CI](https://github.com/thorstentepper/keep-rollin/actions/workflows/ci.yml/badge.svg)](https://github.com/thorstentepper/keep-rollin/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/thorstentepper/keep-rollin/branch/main/graph/badge.svg)](https://codecov.io/gh/thorstentepper/keep-rollin)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![Keep Rollin' dashboard](docs/img/dashboard.png)

## Description

Computes annualised risk/return metrics for one or more assets against a configurable benchmark:

- **Sharpe ratio** — excess return per unit of total volatility
- **Sortino ratio** — excess return per unit of downside volatility (doesn't penalise upside)
- **Max drawdown** — largest peak-to-trough decline over the period
- **Rolling Sharpe ratio** — Sharpe ratio computed over a sliding window (default: 63 trading days ≈ 1 quarter)
- **Rolling Sortino ratio** — same, but penalising only downside volatility within each window

Data is fetched live from Yahoo Finance, so any ticker and date range can be analysed without managing local CSV files. If Yahoo Finance is unavailable, the dashboard falls back to a small price snapshot shipped with the package so it still renders — clearly flagged as offline data.


## Installation

```bash
uv sync --all-extras          # library + CLI + dev tools + Streamlit + API
```

Or install a minimal set:

```bash
uv sync --extra dev           # library + CLI + dev tools only
```


## Usage

### Streamlit app

```bash
uv run streamlit run streamlit_app.py
```

Opens an interactive dashboard in your browser: pick tickers, benchmark, date range, and rolling window from the sidebar and click **Analyse**.

It opens on MSFT and NVDA against the S&P 500, over the five years ending on the previous trading day. Trading days are approximated as weekdays, so the default end date does not skip exchange holidays.

### Docker

The Dockerfile has two runtime targets. The dashboard is the default:

```bash
docker build -t keep-rollin .
docker run --rm -p 8501:8501 keep-rollin
```

Then visit <http://localhost:8501>.

The API is a separate target:

```bash
docker build --target api -t keep-rollin:api .
docker run --rm -p 8000:8000 keep-rollin:api
```

Then visit <http://localhost:8000/docs>.

| Target | Serves | Port | Healthcheck |
|--------|--------|------|-------------|
| `dashboard` (default) | Streamlit dashboard | 8501 | `/_stcore/health` |
| `api` | FastAPI JSON API | 8000 | `/health` |

They are separate images rather than one image with an overridable command because `CMD`, `EXPOSE` and `HEALTHCHECK` are baked in at build time — a single image would report itself unhealthy for whichever service it was not built for. The two targets share a dependency base, so building both is barely slower than building one, and each carries only its own extra: the API image has no Streamlit, the dashboard image has no FastAPI.

**The `rollin` CLI ships in both images**, since it installs with the package. Override the command to use it without starting a server:

```bash
docker run --rm keep-rollin rollin MSFT NVDA --start 2023-01-01 --end 2024-01-01
```

Both images run as a non-root user and include the bundled offline price snapshot, so the fallback works in the container too.

**Installing Docker.** On Debian/Ubuntu (including WSL2), the distro packages are enough:

```bash
sudo apt install docker.io docker-buildx
sudo usermod -aG docker $USER   # then log out and back in, or run: newgrp docker
```

`docker-buildx` is not optional here. The build needs [BuildKit](https://docs.docker.com/build/buildkit/): the Dockerfile opens with a `# syntax=docker/dockerfile:1.6` frontend directive and uses `RUN --mount=type=cache` to reuse uv's download cache between builds. Any Docker with buildx available works — Docker CE from [Docker's apt repository](https://docs.docker.com/engine/install/ubuntu/) and Docker Desktop both ship it too, and are worth preferring if you want upstream-latest releases or a GUI.

Avoid the Docker snap under WSL: snapd is unreliable there. `podman-docker` runs containers fine but is a CLI emulation — Buildah ignores the `# syntax=` directive, so it does not validate this Dockerfile faithfully.

On WSL2 the daemon needs systemd, which is enabled by putting this in `/etc/wsl.conf` and running `wsl --shutdown` from PowerShell:

```ini
[boot]
systemd=true
```

### CLI

```bash
rollin MSFT NVDA --benchmark ^GSPC --start 2023-01-01 --end 2024-01-01
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--benchmark` | `^GSPC` | Yahoo Finance symbol for the benchmark |
| `--start` | required | Start date `YYYY-MM-DD` |
| `--end` | required | End date `YYYY-MM-DD` |
| `--rolling-window` | `63` | Rolling window in trading days (for both Sharpe and Sortino) |
| `--plot` | off | Display rolling Sharpe and Sortino ratio charts |


### HTTP API

```bash
uv sync --extra api
uv run uvicorn keep_rollin.api:app --reload
```

Interactive docs at <http://localhost:8000/docs>.

```bash
curl "http://localhost:8000/metrics?tickers=MSFT&tickers=NVDA&start=2023-01-01&end=2024-01-01"
```

| Endpoint | Description |
|----------|-------------|
| `GET /metrics` | Same metrics as the CLI, as JSON — one object per asset |
| `GET /health` | Liveness probe; also reports whether the offline snapshot is present |

Query parameters for `/metrics`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tickers` | `MSFT`, `NVDA` | Yahoo Finance symbol; repeat the parameter for several |
| `start` | 5 years before `end` | Start date `YYYY-MM-DD` |
| `end` | previous trading day | End date `YYYY-MM-DD` |
| `benchmark` | `^GSPC` | Benchmark symbol |
| `rolling_window` | `63` | Rolling window in trading days (2–252) |

Every parameter is optional and each defaults independently, so `curl http://localhost:8000/metrics` is a valid request that returns the same defaults the dashboard opens on.

The response includes `used_fallback`, which is `true` when live data was unavailable and the offline snapshot was served instead. Metrics that are mathematically undefined for the data (an infinite Sortino ratio, for instance) are returned as `null`.

Price fetches are cached in-process for 15 minutes, keyed on tickers, benchmark and date range — daily closes don't change intraday, and this keeps repeated requests off Yahoo Finance's rate limiter. Responses carry an `X-Cache: HIT|MISS` header. Offline-snapshot results are cached for only 60 seconds, so the API returns to live figures shortly after Yahoo Finance recovers. The cache is per-process, so it is not shared across multiple workers.

### Refreshing the offline snapshot

The bundled snapshot backs the dashboard when Yahoo Finance is unavailable. Regenerate it with:

```bash
uv run python scripts/refresh_fallback.py
```

It refuses to overwrite the existing snapshot if the fetch fails or returns too little data, so a bad run cannot destroy the safety net. Pass tickers and `--benchmark` / `--start` / `--end` to change what it covers.


## Running tests

```bash
uv run pytest
# with coverage
uv run pytest --cov=keep_rollin
```


## Project structure

```
.github/workflows/ci.yml       — pytest on push/PR (Python 3.10 and 3.13)
Dockerfile                      — multi-stage build; dashboard and api targets
streamlit_app.py               — Streamlit dashboard
scripts/
    refresh_fallback.py        — regenerate the offline price snapshot
src/keep_rollin/
    data.py                    — fetch adjusted close prices, with offline fallback
    metrics.py                 — Sharpe, Sortino, max drawdown, rolling variants, shared summary
    cli.py                     — command-line entry point
    api.py                     — FastAPI layer exposing the same metrics over HTTP
    resources/
        fallback_prices.parquet — offline snapshot used when Yahoo Finance is down
tests/
    test_api.py
    test_data.py
    test_metrics.py
pyproject.toml
```


## Credits

The project began as a DataCamp exercise on the Sharpe Ratio (original tasks by Stefan Jansen, completed in January 2022). Everything in this repository — the package structure, Sortino and rolling-window metrics, CLI, Streamlit app, containerisation, and CI — was written from scratch.
