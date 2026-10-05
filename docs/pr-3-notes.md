# PR 3 notes: CMS readers

Decisions made while building, without questions to Alex (subagent run, 2026-10-05).

1. **Synthetic fixtures only.** No CMS file was downloaded. The readers are tested on hand-made
   files shaped like the documented layouts (`fixtures/cms/SOURCE.md`). Real extracts follow Alex's yes.
2. **Column names are data.** `cms/layouts.py` holds one layout per file per year. 2027 starts as a
   copy of 2026. The CMS pages list no columns (checked the 2027 Crosswalk, PBP 2027, and Landscape
   pages), so names come from past releases and are marked unconfirmed in `docs/cms-fields.md`.
3. **Premium comes from the Landscape, not PBP.** PBP Section D has only the Part C premium.
4. **Everything is read as text first** so plan ids keep leading zeros; money is then cast to an
   exact decimal with 2 places. Dollar signs, commas, and spaces are stripped; empty means missing.
5. **Never guess.** An unknown crosswalk label, a consolidated row without a new plan id, a missing
   column, an unknown year, or two PBP rows for one plan each raise `CmsFileError` naming the file.
6. **Crosswalk labels reuse PR 1's `crosswalk_status_from_cms`**, so the label list lives in one place.
   The original CMS label and the row number are kept as evidence for the flag (SPEC example 3).
7. **Plan id format.** Segment 000 is dropped (H0028-030); any other segment is kept (H0028-030-001),
   matching PR 1's PlanId pattern.
8. **Readers return polars DataFrames**, not models. PR 7 and PR 8 decide how rows become citations.
9. **config.py created here** with a `# PR 3` block (no earlier PR had made it).

Files Alex will need to approve before the real run (CMS pages state no sizes):
- `pbp-benefits-2026.zip` and `pbp-benefits-2027.zip` (benefits-data pages)
- `cy2026-landscape-202609.zip` and `cy2027-landscape-202609-1.zip` (prescription-drug-coverage page)
- `plan-crosswalk-2027.zip` (2027 Part C and D Plan Crosswalk page)
