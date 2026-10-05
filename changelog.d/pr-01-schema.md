## PR 1: Canonical plan schema and provenance (2026-10-05)

- New `plan_diff.models` package: plan ids, citations, the 15 v1 fields with typed values, plan records, sources manifest, validation results, plan diffs with CMS crosswalk status, and review items.
- Money is always an exact decimal with 2 places. A float is refused.
- Every model refuses unknown fields and cannot be changed once made.
- New command `plan-diff schema export --out <folder>` writes one JSON Schema file per run output model.
- docs/schema.md explains every field in plain language.
