# Architecture decision records

One short file per lasting decision, named `NNNN-short-name.md`, with context, the decision, and its
consequences. None are written yet. Planned:

- 0001: PDF text and table extraction library, chosen for license fit with MIT (PyMuPDF is AGPL, so
  it is out unless the license changes).
- 0002: Canonical plan schema and the page provenance carried by every field.
- 0003: Deterministic extraction first; Jev and LLMs as a checked fallback, never the final word.
- 0004: CMS public use files as ground truth for the accuracy table.
- 0005: Plan year diff keyed by plan ID, with change categories and a "shop again" flag.
- 0006: Static-first dashboard that renders a committed demo run.
- 0007: Public data only, and how downloaded documents are stored (data/raw/, never committed in bulk).
