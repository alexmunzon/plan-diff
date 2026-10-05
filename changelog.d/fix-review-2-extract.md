## Fix: review 2, extraction (2026-10-05)

- Period words (monthly, a year) set the unit only for the dental and OTC allowances. A note such as "does not include your monthly premium" no longer turns a yearly amount into a monthly one.
- A label with no value never takes the next row's value, and an unreadable row beside a readable one is flagged as a conflict at low confidence.
- A "Deductible" row inside a drug section is never read as the medical deductible.
- "Not covered (you pay 100%)" reads as not covered. Inpatient takes the in-network value first, and any day range means per day.
- The unit comes only from the chosen value's own words. An allowance with no stated period has no unit and goes to review instead of defaulting to a year.
- Footnote marks after an amount are stripped; a digit that might be a footnote lowers confidence and goes to review.
