# 0002. Restructure the notebook as an installable package

**Status:** Accepted — 2026-05-16
**Decision:** Move the code into an installable package under `src/`, with the
metrics, data access and entry point as separate modules.

## Context

The original was a notebook plus a flat `functions.py` and `app.py` at the
repository root. Importing anything depended on the current working
directory, and there was no boundary between the calculations and the way
they were presented.

## Considered options

- **`src/` layout, installed package** — chosen. The package is importable
  only when installed, so tests exercise the built artefact rather than a
  directory that happens to be on `sys.path`.
- **Flat layout at the repository root** — rejected. Simpler, but it hides
  packaging mistakes: a module or data file left out of the wheel still works
  locally and fails for everyone else.

## Consequences

- Packaging errors surface early. The bundled parquet snapshot from
  [0007](0007-ship-an-offline-price-snapshot-as-a-fallback.md) is only
  reachable at runtime because the layout forced the question of what ends up
  inside the wheel.
- Anything that runs the code must install it first, which is what makes the
  editable install in
  [0014](0014-install-editable-for-pip-based-hosts.md) necessary on hosts
  that skip reinstallation.
- Separating metrics from presentation is what later made one shared
  implementation across three surfaces possible
  ([0008](0008-share-one-implementation-across-all-surfaces.md)).
