## PR 03: Readers for CMS public files (2026-10-05)

- New `plan_diff.cms` readers for the Part C and D Plan Crosswalk, the MA Landscape, and PBP benefits, built on polars.
- Money is read as an exact decimal. Crosswalk labels map onto the plan schema's crosswalk status, and an unknown label stops the read instead of being guessed.
- Column names live in a per-year layout, so a 2027 file that renames a column needs a data change, not new code.
- Small hand-made synthetic fixtures in `fixtures/cms/` (no CMS data downloaded yet).
- `docs/cms-fields.md` maps each of the 15 fields to its CMS file and column.
