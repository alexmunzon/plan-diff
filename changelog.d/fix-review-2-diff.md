## Fix: review 2, diff and shop-again flag (2026-10-05)

- The shop-again flag is never confidently wrong. If premium, maximum out-of-pocket, drug deductible,
  or a removed benefit is missing, read with low confidence, in the wrong unit, not comparable, or
  disagrees with CMS, it goes to review as high severity and cannot decide the flag. With no other
  confident reason the flag is undecided instead of off.
- `diff_plans` takes the CMS validation results as an optional `validation` argument.
- A field missing last year is no longer reported as added; it goes to review.
- County names are compared without case, punctuation, or the word "County". An empty county list
  goes to review instead of reading as every county lost.
- CMS citations name the plan year and the real file; the Landscape file name is required.
