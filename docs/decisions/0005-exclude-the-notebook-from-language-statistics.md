# 0005. Exclude the notebook from language statistics

**Status:** Superseded by [0006](0006-drop-the-original-notebook-from-the-repo.md) — 2026-05-16
**Decision:** Mark `notebooks/sharpe_ratio.ipynb` as documentation in
`.gitattributes` so GitHub's language detection does not count it.

## Context

The original DataCamp notebook was kept in the repository as provenance. It is
a large JSON file, so GitHub's Linguist counted it as the dominant language
and labelled the repository Jupyter Notebook — describing the artefact the
project had deliberately moved away from
([0002](0002-restructure-the-notebook-as-an-installable-package.md)).

## Considered options

- **`linguist-documentation` in `.gitattributes`** — chosen. Keeps the
  notebook and its history while stopping it from dominating the language
  statistics.
- **Delete the notebook** — rejected at the time. It was the only record of
  where the project started, and the credits referred to it.
- **Accept the mislabelling** — rejected. The language badge is the first
  thing a visitor reads.

## Consequences

- The repository presents as Python.
- A `.gitattributes` file now exists solely to compensate for a file nothing
  else needs, which is a hint that the underlying arrangement is the problem
  rather than the labelling.
