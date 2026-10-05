## PR 07: Validation against CMS, accuracy table, review queue (2026-10-05)

- Every extracted field is checked against CMS data: match, mismatch, not in CMS, or not extracted.
  `validation.json` keeps the PDF value, the CMS value, the PDF page, and the CMS file row.
- A disagreement is flagged, never resolved: both values go to `review_queue.jsonl` with low
  confidence (SPEC example 4).
- `accuracy.json` counts matches and mismatches per field and per extraction method.
- Allowances compare as yearly amounts; an allowance whose period CMS does not give goes to review.
