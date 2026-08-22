# 0011. Deploy the dashboard to Streamlit Community Cloud

**Status:** Accepted — 2026-08-15
**Decision:** Host the dashboard on Streamlit Community Cloud, adding a
`requirements.txt` because the platform installs with pip and cannot read
`uv.lock`.

## Context

A portfolio project benefits disproportionately from a link someone can click.
Hosting had to cost nothing, and the repository is public, which is the
condition Community Cloud attaches to its free tier.

## Considered options

- **Streamlit Community Cloud** — chosen. Free for public repositories, no
  infrastructure to run, and it deploys the dashboard directly from a branch.
- **Fly.io** — rejected for now. It would deploy the existing Dockerfile and
  could host the API too ([0009](0009-build-separate-docker-targets-per-service.md)),
  but its free allowance no longer covers this reliably, and "free" was the
  binding constraint.

## Consequences

- A `requirements.txt` now exists alongside `pyproject.toml` purely for this
  host, duplicating dependency information
  ([0003](0003-use-uv-and-hatchling-for-packaging.md)).
- Only the dashboard is hosted. The API has no public deployment.
- Community Cloud sleeps idle apps, so the first visitor after a quiet period
  waits for a cold start — the same conditions under which the upstream fetch
  is most likely to fail, which the fallback covers
  ([0007](0007-ship-an-offline-price-snapshot-as-a-fallback.md)).
- The deployment tracks a branch by name, so renaming the default branch
  breaks it until it is repointed.
