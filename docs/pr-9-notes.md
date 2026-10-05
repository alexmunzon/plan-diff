# PR 9 notes: run command, run folder, CMS unzip, demo

Decisions made while building, without questions to Alex (subagent run, 2026-10-05).

1. **CMS folder names.** `--cms` holds `landscape_<year>.csv`, `pbp_<year>/`, and
   `crosswalk_<new year>.csv`, the names `fixtures/cms/` already used. A missing file is not an
   error: its fields are "not in CMS", and with no crosswalk every diff is undecided. PR 15 maps the
   real unzipped CMS folders to these names.
2. **2027 fixtures added** (`landscape_2027.csv`, `pbp_2027/`, hand-typed, synthetic, noted in
   `fixtures/cms/SOURCE.md`). Without a 2027 landscape the new year has no counties, which would
   read as a lost service area.
3. **Years.** One year (no diff) or two years in a row. Anything else is refused.
4. **Document ids** are the PDF file name without `.pdf`. Two PDFs with the same name are refused,
   because their citations would clash.
5. **Several documents for one plan year.** Each field comes from the first document type that
   has it (SB, then EOC, then ANOC, `config.RUN_DOCUMENT_PRIORITY`). A different value in another
   document goes to review as `conflicting_values`; a field is reported missing only when no
   document had it.
6. **Documents that are not used.** Unsure ones go to review (the classifier's item) and are not
   extracted, because they cannot be tied to a plan year. Unreadable ones (any exception from the
   PDF libraries: corrupt, password protected) become a high severity `unclassified_document` item
   saying "could not open". Classified documents outside `--plans` or `--years` are listed in the
   manifest as `outside_slice`.
7. **Diff lookup.** The new record is found only through the crosswalk's current plan id. A
   crosswalk row that points at a plan with no new-year document gives an undecided diff with a high
   `not_extracted` item. A requested plan with no old-year document is not diffed and goes to review.
   The terminal summary prints undecided as "undecided, needs review", never "no".
8. **Plan name** comes from the CMS Landscape; with no Landscape row it is the plan id.
9. **Immutable folder.** Written into a hidden temp folder next to the target and swapped in at
   the end. An existing folder is refused unless `--overwrite`, which deletes only that run id's
   folder. Run ids allow letters, digits, dot, dash, underscore, so a run id cannot escape `--out`.
10. **Timings and determinism.** `--now` freezes the clock: started and finished are that time and
    every step timing is 0. Without it the real clock is used. Input paths in the manifest are
    relative to `--docs` or `--cms`, so the manifest holds no local paths.
11. **Manifest** is a new `RunManifest` model (added to `TOP_LEVEL_MODELS`, so schema export writes
    7 files). Rules are "on"; Jev and LLM modes are "off" (`config.RUN_JEV_MODE`,
    `RUN_LLM_MODE`), 0 calls, cost as Decimal "0.00". Versions list plan-diff, pdfplumber, pypdf,
    polars, and pydantic (pinned by uv.lock).
12. **plans.parquet** has one row per plan, year, and field. `amount` is Decimal(12, 2) and
    `percent` Decimal(5, 2); only `confidence` (a score) is a float.
13. **CMS unzip** is its own command, `plan-diff unzip-cms --raw data/raw`, not part of fetch, so
    fetch's tests and behavior are unchanged. Each zip goes to `data/raw/<zip name>/` with a
    `.source-sha256` marker. It refuses absolute paths, drive letters, `..`, symlinks, more than
    `UNZIP_MAX_MEMBERS` members, and more than `UNZIP_MAX_BYTES` (checked from the header and again
    while writing). It never deletes a folder that has no marker.
14. **Demo.** `npm run demo` runs `engine/tests/demo_run.py` (it needs reportlab, a dev
    dependency, so it lives beside `pdf_factory`). PDFs are written with reportlab's invariant mode
    into a temp folder that is deleted afterwards; only `.json` and `.jsonl` files are copied to
    `dashboard/public/demo-run/` (no parquet). The demo makes 2026 SBs for H9999-001, -002, -003,
    a 2027 SB only for H9999-001 (the crosswalk ends -002 and -003, so a 2027 document for them
    would describe a plan that does not exist), and one SB with no plan id to show the review path.
15. **Jev and LLM** are off. Nothing in this PR calls them.

## Risks and follow-ups

- Review 2 is merged: the run passes every validation result to `diff_plans(validation=...)`, so
  a threshold field that disagrees with CMS leaves the flag undecided (tested in test_run.py).
- Allowances are always "period not comparable" against CMS (PR 7 decision), so the demo's review
  queue holds 6 allowance items. They are noise until the CMS period columns are read.
- Catching every exception from the PDF libraries keeps the run alive, but a bug in our own
  classifier would also show up as "could not open". The review item names the exception type.
