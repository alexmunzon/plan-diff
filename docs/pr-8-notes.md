# PR 8 notes: diff engine and shop-again flag

Decisions made while building, without questions to Alex (subagent run, 2026-10-05).

1. **Undecided is `shop_again = None`.** `PlanDiff.shop_again` is now `bool | None` and
   `crosswalk_status` is `CrosswalkStatus | None`. With no crosswalk row the diff has only the old
   plan id, no changes, no reasons, and one `ReviewItem` of new kind `crosswalk_row_missing`
   (severity high). The model refuses an undecided diff with no review item, and a decided diff
   with no crosswalk status. Two new fields default to empty, so older JSON still loads:
   `evidence` (the CMS crosswalk row as a citation, method `cms`, page = 1-based file row, text =
   the CMS label) and `review`.
2. **The crosswalk is the only map.** Without a row, even a new-year record with the same plan id is
   not compared (it stays undecided). With a row, the records must agree with it (old id, new id,
   year) or `diff_plans` raises; a non-terminated row with no new record also raises.
   `crosswalk_row_for(frame, old_id, file_name)` turns the PR 3 reader output into a `CrosswalkRow`
   and refuses two rows for one old id.
3. **Direction renamed** to up, down, same, added, removed, not_comparable (was increased,
   decreased, added, removed, changed). Nothing outside the models test used the old names.
   `ADDED` now also covers "not covered last year, covered now". Categories keep their PR 1 names
   (copays, drugs, allowances).
4. **Every field present in either year is listed**, including unchanged ones (`same`), so the
   comparison page can show all fields side by side.
5. **Comparing.** Different kinds (copay vs coinsurance, money vs copay) or different units on a
   non-allowance field are not comparable and never flag. Allowances are compared after
   `annualize`; a unit that is not a period (or no unit) is not comparable.
6. **Reasons.** "plan terminated", "plan consolidated into H9999-001", "service area lost 1 county:
   Comal", "service area reduced (CMS crosswalk)" (the status, when no county list shows the loss),
   "dental allowance no longer covered", "dental allowance removed", "premium up $25 a month",
   "maximum out-of-pocket up $1,000", "drug deductible up $50". Amounts show cents only when there
   are some.
7. **Thresholds** in `config.py` under `# PR 8`, as Decimal: premium 20.00, MOOP 1000.00, drug
   deductible 0.01 (any rise). A rise equal to the threshold flags.

## Risks and follow-ups

- "Field absent in the new year" flags as removed per the brief, but absence can also be an
  extraction miss. PR 9 should check the new year's `not_extracted` review items and treat such a
  removal as needing review rather than a firm flag.
- A premium recorded with a non-monthly unit is not comparable and would not flag.
- Real crosswalk rows may split one old plan into several; `crosswalk_row_for` refuses that today.
