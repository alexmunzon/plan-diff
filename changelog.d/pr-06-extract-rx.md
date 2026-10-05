## PR 06: Deterministic extraction, drugs and allowances (2026-10-05)

- Reads the drug deductible, drug tiers 1 to 3, the dental allowance, and the OTC allowance, so all
  15 v1 fields now come out of a Summary of Benefits with their page.
- Drug tiers use the standard retail 30-day price. A cell with a standard and a preferred pharmacy
  price takes the standard one, lowers confidence, and records the choice in review.
- New allowance period "per quarter", and `annualize` to compare allowances as yearly amounts
  ($50 a quarter is $200 a year).
- A missing field is never guessed; it goes to review.
