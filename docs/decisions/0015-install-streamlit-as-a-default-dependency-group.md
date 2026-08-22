# 0015. Install Streamlit as a default dependency group

**Status:** Accepted — 2026-08-23
**Decision:** Declare Streamlit in a PEP 735 dependency group listed in
`default-groups`, rather than as an optional extra, and delete
`requirements.txt`. Supersedes
[0014](0014-install-editable-for-pip-based-hosts.md).

## Context

Streamlit Community Cloud changed how it installs dependencies. Its build log
now reads:

```
WARN: More than one requirements file detected. Available options:
  uv-sync uv.lock, uv requirements.txt, poetry pyproject.toml.
  Used: uv-sync with uv.lock
```

It prefers `uv.lock` over `requirements.txt`, and runs a bare `uv sync`. That
installs the project's dependencies and its default groups — but **not** its
optional extras. Streamlit lived in the `app` extra, so it was never
installed, and the app failed to start:

```
sudo: /home/adminuser/venv/bin/streamlit: command not found
```

Nothing in the repository had changed. The host changed, and the arrangement
from [0014](0014-install-editable-for-pip-based-hosts.md) — an editable
install declared in `requirements.txt` — stopped being consulted at all.

This is the same trap as before, from the other direction: `uv sync` is exact
rather than additive ([0003](0003-use-uv-and-hatchling-for-packaging.md)), and
here the host was the one doing the syncing.

## Considered options

- **A default dependency group** — chosen. Groups are installed by a bare
  `uv sync`; extras are not. The host needs no configuration and no second
  dependency file, so there is nothing left to fall out of step.
- **Move Streamlit into the base dependencies** — rejected. It would work
  everywhere, but the API container and a CLI-only install would both carry
  Streamlit for no reason, losing the per-image leanness of
  [0009](0009-build-separate-docker-targets-per-service.md).
- **Delete `uv.lock` so the host falls back to `requirements.txt`** — rejected.
  It restores the old behaviour by removing the lockfile CI and Dependabot
  depend on, trading reproducibility for a workaround.
- **`[tool.uv] default-extras`** — not available. uv rejects the key outright.

## Consequences

- A bare `uv sync` — the host's, and anyone's — installs Streamlit. Verified
  by syncing into a clean environment and checking for the binary.
- The API image opts out with `--no-default-groups`, so it still carries no
  Streamlit. The dashboard stage no longer needs `--extra app` at all.
- `uv sync --extra dev` now also installs Streamlit, since default groups
  always apply. A genuinely minimal install needs `--no-default-groups`.
- `requirements.txt` is gone. It was already being ignored, and its presence
  is what produced the host's multiple-files warning.
- The editable install of [0014](0014-install-editable-for-pip-based-hosts.md)
  goes with it. That decision solved a real problem for a pip-based host; this
  host no longer uses pip, so the reasoning no longer applies. If a future
  host does, the stale-package failure described there will apply again.
