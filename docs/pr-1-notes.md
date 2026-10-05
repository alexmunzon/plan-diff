# PR 1 notes: schema decisions

- **Path.** All models live in `engine/src/plan_diff/models/` and are re-exported from `plan_diff.models`.
  Later PRs should import from the package, not the submodules.
- **Base class.** `StrictModel` (extra fields forbidden, frozen) copied in spirit from agency-intake-kit's
  `lineage.py`. Kept local rather than imported, because the shared schema package does not exist yet.
- **PlanId uses `[0-9]`, not `\d`.** Pydantic's regex engine treats `\d` as any Unicode digit, so
  `\d` would have accepted Arabic-Indic digits. A test covers it. Only `H` contracts are accepted, per
  the SPEC slice; Part D only (`S`) and regional PPO (`R`) ids would need a later change.
- **Money.** `Money`, `Copay`, and `Coinsurance` refuse floats (and booleans) before parsing, refuse
  more than 2 decimal places, and always store 2 places (25 becomes 25.00). JSON stores money as a
  string, so it round-trips exactly. Amounts must be 0 or more.
- **Field values are tagged.** Each value carries a `kind` (money, copay, coinsurance, not_covered),
  so JSON says which kind it is and loads back without guessing. The unit sits on `ExtractedField`,
  not on the value, and may be empty (for example, not covered).
- **Confidence is a float** from 0 to 1. It is a score, not money.
- **Citation page for CMS rows.** For method `cms`, `document_id` is the CMS file name and `page` is
  the 1-based row number. One shape for every citation keeps the review queue simple.
- **PlanRecord** refuses a field stored under the wrong key, and a rule or LLM citation that points at
  a document not listed in `documents`. A missing field means "not extracted".
- **SourceDocument.** `sha256`, `size_bytes`, and `retrieved_at` are empty until the first fetch. Once
  `sha256` is set, size and date must be set too. `retrieved_at` must carry a time zone. The manifest
  refuses duplicate document ids and has `schema_version: 1`.
- **ValidationResult** checks that the verdict fits the values (match needs equal values, mismatch
  needs different values, not_in_cms needs a PDF value and no CMS value, not_extracted needs no PDF
  value). It carries both citations: the PDF page and the CMS row (SPEC decision 5).
- **FieldChange** holds the old and new `ExtractedField`, so the pages travel with every change. Its
  category must equal `category_for(field)`. Categories follow SPEC section 8: premium, deductible,
  moop, copays, drugs, allowances. Medical deductible got its own category rather than being folded
  into premium or moop.
- **PlanDiff** adds `old_year` and `new_year` (new must be old + 1). New plans have no old id;
  terminated plans have no new id; every other status, including consolidated, needs both.
  `shop_again` is true exactly when `reasons` is not empty.
- **CrosswalkStatus mapping** (from the research file, section 1c, CMS guidance and 42 CFR 422.530):
  New Plan to new; Renewal Plan to continuing; Consolidated Renewal Plan to consolidated; Renewal
  Plan with SAR to service_area_reduced; Renewal Plan with SAE to service_area_expanded (added beyond
  the brief's list, because CMS uses it); Terminated/Non-renewed plan or contract to terminated.
  `crosswalk_status_from_cms` raises on an unknown label. Not yet checked against the real file's
  codebook: PR 3 must confirm the exact label text and add any codes.
- **ReviewItem** kinds: pdf_cms_mismatch, rule_llm_disagree, not_extracted, unclassified_document.
  Plan, year, and field may be empty for a document that could not be classified.
- **Schema export** writes `<Model>.schema.json` for the five run output models: SourcesManifest,
  PlanRecord, ValidationResult, PlanDiff, ReviewItem. Nested models appear in each file's `$defs`.

## Risks

- Crosswalk labels are unconfirmed (see above). Mapping is one dict, easy to change in PR 3.
- `PlanRecord.fields` is a dict, so the model is frozen but the dict inside is not. Treat it as
  read only.
