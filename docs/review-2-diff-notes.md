# Review 2 notes: the shop-again flag is never confidently wrong

Decisions made while fixing review 2 findings, without questions to Alex (subagent run, 2026-10-05).
The rule, from the orchestrator and SPEC decision 5 ("flag it, never pick"): a field that cannot be
trusted never decides the flag. It goes to review instead.

1. **Deciding fields.** The threshold fields (premium, maximum out-of-pocket, drug deductible) and
   any benefit that reads as removed. A deciding field is uncertain when, in either year, it is
   missing, below `config.SHOP_AGAIN_CONFIDENCE_FLOOR` (0.7; a value at 0.7 is trusted), in a unit
   other than the one in `config.VALIDATE_CMS_UNITS` (premium per month, MOOP and drug deductible
   per year), has a CMS mismatch, or the two years are different kinds of value.
2. **What happens.** An uncertain field gets one review item of new kind `shop_again_uncertain`,
   severity high, naming the field and every reason, with the PDF pages (and the CMS row for a
   mismatch). Its rise or removal is never used as a reason. Then: any confident reason (for example
   a termination, consolidation, lost county, or another field's rise) still gives shop_again True,
   with the uncertain field listed in review. With no confident reason the flag is None (undecided).
3. **The model enforces it.** `PlanDiff` refuses shop_again False while a high
   `shop_again_uncertain` item is present. An undecided diff now needs a high review item and no
   reasons; it may keep its changes when a crosswalk row exists, so the comparison page still shows
   every field. With no crosswalk row it still has no changes.
4. **F1 probe.** MOOP $3,400 per year to $8,850 per month, premium $0 per month to $45 per year: was
   False with no review; now None with two high items. Same unit in both years but the wrong one
   (premium per year both years) is also uncertain, because the monthly threshold cannot apply.
5. **F3, new parameter.** `diff_plans(old, new, crosswalk_row, service_area_old, service_area_new,
   *, validation=None)`. `validation` is the PR 7 `ValidationResult` list (from
   `validate.compare`) for the old and new records; results for other plans or years are ignored,
   and only MISMATCH counts. It is keyword-only and optional so older calls work, but then CMS
   disagreement is not checked (confidence and units still are). The run command (PR 9) should pass
   both years' results.
6. **F6.** A field missing last year and present this year is `not_comparable`, never `added`, with
   a medium `not_extracted` review item dated last year. `added` now means only "explicitly not
   covered last year, covered now"; the FieldChange model refuses `added` with no old value. For a
   threshold field it is the high item instead, and the flag cannot be False. A threshold field
   missing in both years is also uncertain.
7. **F7, counties.** Names compare after lowercasing, turning punctuation into spaces, and dropping a
   trailing "county" (`config.COUNTY_SUFFIXES`); `diff.same_county` is the rule. A lost county is
   reported with last year's spelling. An empty county list for either year gives a high
   `shop_again_uncertain` item (field empty) and never a "lost every county" reason; a CMS
   "service area reduced" status is still a confident reason.
8. **F12, CMS citations.** Each CMS citation keeps the real file name as `document_id` and the row as
   `page`, and its text now says the source, plan year, file, and row, for example
   "CMS PBP 2026, pbp_b7_health_prof.txt, row 1". `cms_values_for` refuses a Landscape frame without
   `landscape_file`; the old "landscape" default is gone.

## Risks and follow-ups

- Real extraction confidences below 0.7 (for example a cell with two values, 0.6) now make the flag
  undecided more often. That is on purpose; tune the floor after the first real run.
- County names are compared without the state. Two same-named counties in different states would
  match; plans in this project are single-state today.
- Without `validation`, a CMS mismatch cannot stop a confident-looking rise. PR 9 must pass it.
- A premium or deductible stored as a coinsurance is not caught by the unit check (both years the
  same kind and right unit); the CMS check would catch it.
