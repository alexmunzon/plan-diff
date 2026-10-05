# PR 7 notes: validation against CMS, accuracy table, review queue

Decisions made while building, without questions to Alex (subagent run, 2026-10-05).

1. **Shape.** `plan_diff.validate` has `cms_values_for` (CMS reader output to one value per field,
   each cited by CMS file name and 1-based data row), `compare` (one ValidationResult per v1
   field), `review_items` (one item per mismatch), `accuracy`, and three writers:
   `validation.json`, `accuracy.json`, `review_queue.jsonl`.
2. **The rules live in the model.** `models.disagreement` decides match or mismatch, and the
   ValidationResult check uses the same function, so a result can never claim a verdict its values
   do not support. Rules: money and copays exact to the cent; a copay never equals a coinsurance;
   not covered equals not covered; allowances compare after `annualize()` when both sides name a
   period, else mismatch "period not comparable"; other fields must also agree on unit when both
   name one ("$295 per stay" vs CMS "$295 per day" is a mismatch).
3. **Model additions** (all optional, old JSON still loads): ValidationResult gains `pdf_unit`,
   `cms_unit`, `reason`; ReviewItem gains `confidence`; new `AccuracyRow` and `AccuracyTable`
   (added to `TOP_LEVEL_MODELS`, so schema export writes 6 files).
4. **CMS units** per field are in `config.VALIDATE_CMS_UNITS`. Dental and OTC have no CMS period
   yet (the period columns are not read, docs/cms-fields.md), so every allowance with a dollar
   amount is a "period not comparable" mismatch until those columns are read. This is noisy on
   purpose: guessing a year could hide a real disagreement.
5. **Premium** comes from the Landscape. Counties that give one plan different premiums stop the
   run with `CmsFileError` naming the rows. A CMS "N/A" is not in CMS; "Not covered" is NotCovered.
6. **Readers** now keep `source_row` (Landscape and PBP) and `file` (PBP) so the CMS citation can
   name the row.
7. **Review item:** kind `pdf_cms_mismatch` already existed; evidence is the PDF page then the CMS row;
   reason states both values and why; confidence 0.3; severity high for premium, MOOP, and drug
   deductible (the shop-again fields), medium otherwise.
8. **Accuracy:** per field and per method, then one total row per method. Match rate is matched
   over matched plus mismatched; None when nothing was compared. A field nobody extracted counts
   under `rule`, since the deterministic pass always runs.
9. **Review queue order:** severity (high first), plan id, field in v1 order; Python's stable sort
   keeps input order on ties. Document-level items sort first within their severity.

No new dependencies.

## Risks and follow-ups

- CMS column names are still unconfirmed; real files may change which fields can be compared.
- Coinsurance plans read as a CMS copay (or missing) until the `coins_pct` columns are read, which
  will show as copay vs coinsurance mismatches.
- Units are a field-level assumption on the CMS side; PR 15 should check them on real files.
- NOT_EXTRACTED results do not add review items here; extraction already adds them.
