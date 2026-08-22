# syntax=docker/dockerfile:1.6

# Two runtime targets share one dependency base:
#
#   docker build -t keep-rollin .                          # dashboard (default)
#   docker build --target api -t keep-rollin:api .
#
# They are separate images rather than one image with an overridable command
# because CMD, EXPOSE and HEALTHCHECK are baked in at build time, and the
# dashboard's health probe (Streamlit's /_stcore/health on 8501) is meaningless
# for the API (/health on 8000). One image would report itself unhealthy for
# whichever service it was not built for.
#
# Both images include the `rollin` CLI, which installs with the package.

# ── Shared build base ────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build-base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# ── Dashboard build ──────────────────────────────────────────────────────────
FROM build-base AS build-dashboard

# Dependencies first, so a source-only change does not re-resolve them.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY src ./src
COPY streamlit_app.py ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# ── API build ────────────────────────────────────────────────────────────────
# --no-default-groups keeps Streamlit out: it is a default group so the
# dashboard and the deployment host get it without asking, but the API image
# has no use for it.
FROM build-base AS build-api

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra api --no-default-groups

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra api --no-default-groups

# ── Shared runtime base ──────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime-base

RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
USER app

# ── API runtime ──────────────────────────────────────────────────────────────
FROM runtime-base AS api

COPY --from=build-api --chown=app:app /app/.venv /app/.venv
COPY --from=build-api --chown=app:app /app/src /app/src

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

CMD ["uvicorn", "keep_rollin.api:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Dashboard runtime ────────────────────────────────────────────────────────
# Last stage, so a plain `docker build .` still produces the dashboard.
FROM runtime-base AS dashboard

COPY --from=build-dashboard --chown=app:app /app/.venv /app/.venv
COPY --from=build-dashboard --chown=app:app /app/src /app/src
COPY --from=build-dashboard --chown=app:app /app/streamlit_app.py /app/streamlit_app.py

ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status == 200 else 1)"

CMD ["streamlit", "run", "streamlit_app.py"]
