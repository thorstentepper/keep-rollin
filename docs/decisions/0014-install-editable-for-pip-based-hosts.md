# 0014. Install editable for pip-based hosts

**Status:** Accepted — 2026-08-16
**Decision:** Use `-e .[app]` in `requirements.txt` so the deployed app always
imports the checked-out source.

## Context

A plain `.` builds a wheel and copies it into site-packages. The host pulls
fresh application code from git on every deploy but only reruns pip when
`requirements.txt` changes — so a commit that added code to the package
without touching dependencies left the previous deploy's copy installed.

The freshly pulled `streamlit_app.py` then imported names that existed in the
repository and not in that stale copy, and the deployed app died on an
`ImportError` while every check passed locally.

## Considered options

- **Editable install** — chosen. The installed package resolves to the source
  tree, so application code and package code cannot drift apart regardless of
  whether the host reinstalls.
- **Bump the version on every release** — rejected. It works, because pip
  reinstalls when the version changes, but it makes every code change depend
  on remembering a bookkeeping step, and forgetting it fails at deploy time.
- **Restructure to a flat layout so no install is needed** — rejected. It
  would undo [0002](0002-restructure-the-notebook-as-an-installable-package.md)
  to work around a host's caching.

## Consequences

- Deploys pick up package changes reliably; the failure mode is gone rather
  than mitigated.
- Editing `requirements.txt` is itself what triggers the host to reinstall, so
  the fix also cleared the stale environment that exposed it.
- The dependency on the host supporting PEP 660 editable installs is now
  implicit; a host that refuses them would need the version-bump approach.
