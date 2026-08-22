# 0003. Use uv and hatchling for packaging

**Status:** Accepted — 2026-05-16
**Decision:** Declare the project in `pyproject.toml` with hatchling as the
build backend, and manage environments and pinning with uv and `uv.lock`.

## Context

The original repository had a three-line `requirements.txt` and no build
configuration. Turning the code into an installable package
([0002](0002-restructure-the-notebook-as-an-installable-package.md)) required
choosing a build backend, and running it reproducibly in CI required a lock
file.

## Considered options

- **hatchling + uv** — chosen. Hatchling needs almost no configuration for a
  `src/` layout, and uv resolves and installs fast enough that CI can skip
  caching entirely. Optional dependencies group cleanly into extras.
- **pip + `requirements.txt`** — rejected. No build backend, no lock file, and
  no way to express "the dashboard needs Streamlit but the library does not".
- **Poetry** — rejected. Capable, but a heavier toolchain and its own
  metadata dialect for no gain at this size.

## Consequences

- Dependencies split into extras (`dev`, `app`, `api`), so an install can be
  as small as the task needs.
- `uv sync` is exact rather than additive: it removes anything outside the
  requested extras. Naming too few extras silently strips tools the job
  needs, in CI as much as locally.
- Hosts that only speak pip cannot read `uv.lock`, which is why a separate
  `requirements.txt` reappears in
  [0011](0011-deploy-the-dashboard-to-streamlit-community-cloud.md).
