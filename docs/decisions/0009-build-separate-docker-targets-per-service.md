# 0009. Build separate Docker targets per service

**Status:** Accepted — 2026-08-15
**Decision:** Give the dashboard and the API their own runtime targets in one
Dockerfile, sharing a dependency base, rather than shipping one image with an
overridable command.

## Context

Once the API existed alongside the dashboard
([0008](0008-share-one-implementation-across-all-surfaces.md)), the container
had to serve two things that listen on different ports and prove their health
in different ways.

## Considered options

- **Two runtime targets over a shared base** — chosen. `CMD`, `EXPOSE` and
  `HEALTHCHECK` are baked in at build time, so each image can carry the
  correct ones. The expensive dependency layers are shared, so building both
  costs barely more than building one.
- **One image, overridden per service** — rejected. The dashboard's health
  probe is meaningless for the API, so a single image reports itself unhealthy
  for whichever service it was not built for, and every API run has to
  override three settings.

## Consequences

- Each image carries only its own extra: no Streamlit in the API image, no
  FastAPI in the dashboard image.
- The dashboard is the last stage, so a plain `docker build .` still produces
  it and existing commands keep working.
- Two images to build, tag and push instead of one.
- The `rollin` CLI is present in both, since it installs with the package.
- The shared base depends on BuildKit: the Dockerfile opens with a `syntax`
  frontend directive and mounts a cache for the dependency install, so the
  build needs `buildx` available rather than the classic builder. On
  Debian-family systems that is the `docker-buildx` package alongside
  `docker.io`; a builder without it fails on the cache mounts.
