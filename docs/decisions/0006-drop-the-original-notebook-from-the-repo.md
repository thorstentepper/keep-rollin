# 0006. Drop the original notebook from the repo

**Status:** Accepted — 2026-08-09
**Decision:** Delete `notebooks/sharpe_ratio.ipynb` and credit the original
exercise in prose instead. Supersedes
[0005](0005-exclude-the-notebook-from-language-statistics.md).

## Context

The notebook was kept for provenance, and
[0005](0005-exclude-the-notebook-from-language-statistics.md) added
`.gitattributes` rules so it would not skew the repository's language
statistics. Those rules needed revisiting once, and by this point nothing in
the package derived from the notebook: the metrics had been rewritten, two
more had been added, and the data source had changed entirely
([0001](0001-replace-static-csv-data-with-live-market-data.md)).

The notebook had become a file that existed only to be worked around.

## Considered options

- **Delete it, credit the exercise in the README** — chosen. Attribution is
  what actually matters, and prose does that better than a stale artefact.
  The git history still contains the notebook for anyone who wants it.
- **Keep it with the Linguist workaround** — rejected. Maintaining
  configuration to hide a file is a poor trade against simply not shipping it.

## Consequences

- `.gitattributes` lost its only purpose and was removed a week later.
- Provenance now depends on the README and on git history rather than on a
  file in the working tree.
- The repository is smaller and its language statistics are correct without
  any special handling.
