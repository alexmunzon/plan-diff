## PR 8: Diff engine and shop-again flag (2026-10-05)

- New `plan_diff.diff.diff_plans` compares one plan with next year's plan, following the CMS crosswalk only. A consolidated plan is compared with the plan it merged into; a terminated plan has no next-year record.
- A plan with no crosswalk row is never called terminated. The shop-again flag is left undecided and a "crosswalk row missing" item goes to review.
- Every field gets a direction: up, down, same, added, removed, or not comparable (for example a copay that became coinsurance). Allowances are compared as yearly amounts.
- Shop again fires on termination, consolidation, a lost county, a benefit the new year explicitly marks not covered, premium up $20 or more a month, maximum out-of-pocket up $1,000 or more, or any drug deductible rise. Each reason is a plain sentence with the numbers. Thresholds live in `config.py`.
- A benefit simply missing from the new year is not called removed: it may be a reading miss, so it goes to review and does not raise the flag.
