# Review 1 notes: CMS readers and plan ids

Fixes from the first code review, made without questions to Alex (subagent run, 2026-10-05).

1. **One plan id rule** (orchestrator decision A). `models.ids.normalize_plan_id` is the only place
   a plan id is made canonical: contract-plan plus segment, with segment 000 (or none) dropped and
   any other segment kept. H5294-014-001 and H5294-014 are different plans, because segments can
   carry different benefits. The classifier used to drop every segment; it now runs each match
   through the same function. The readers join contract, plan, and segment as text and run each
   distinct value through it too. Short numbers are zero padded (plan "1" is 001).
2. **PlanId is stricter and wider** (decision B). It accepts H (local MA) and R (regional PPO)
   contracts, and it refuses a written-out -000 segment, so one plan has one spelling.
3. **Readers take a slice.** `read_crosswalk`, `read_landscape`, and `read_pbp` now require a
   keyword `plan_ids`. Rows outside the slice are dropped before any check, so Part D (S),
   employer (E), and junk rows for plans nobody asked about never stop a read. A requested id
   that is not an MA id (for example S9999-001) is refused. The crosswalk keeps a row when its
   previous or current id is in the slice.
4. **Money is checked cell by cell before the decimal cast**, on the slice only. "$", spaces, and
   real thousands commas (1,234) are stripped. More than 2 decimal places, a negative value, a
   stray comma, or text that is not a number raises `CmsFileError` naming the file, column, and
   data row. "N/A", empty, and "not applicable" give an empty amount with status `missing`;
   "Not covered" and similar give status `not_covered` (same word as the schema's NotCovered).
   Each reader adds a status column: `premium_status` (Landscape), `amount_status` (PBP).
   The marker lists live under `# Review 1` in config.py.
5. **Duplicate PBP rows** are checked only within the slice. The error names each plan and its
   data row numbers. Rows with a blank contract or plan number are dropped and counted in a
   logged warning ("ignored N rows with a blank plan id"), never reported as duplicates.
6. **A terminated crosswalk row that also names a current plan id** is refused, naming the row.
   The two facts contradict each other and the reader does not pick one.
7. **Messy fixtures** in `fixtures/cms/messy/`, one per reader, test: unpadded plan "1",
   "$1,234", a 3 decimal value (refused), a non-UTF-8 byte (replaced, not fatal), a terminated
   row with a current id (refused), "N/A", "Not covered", a negative value, S, E, and R rows,
   a kept segment, and blank ids. Tests: `engine/tests/unit/test_review_1_cms.py`.

Risks left open:
- Blank-id counts go to a log warning, not into the returned table. PR 7 and PR 8 may want them in
  the run output.
- If a real CMS crosswalk does list a current id on terminated rows, the reader will stop; the
  rule then needs Alex's call, not a silent fix.
- Unknown crosswalk labels outside the slice are now ignored, by design.
