# PR 5 notes: deterministic extraction, cost-sharing fields

Decisions made while building, without questions to Alex (subagent run, 2026-10-05).

1. **Shape.** `plan_diff.extract` has `values.py` (one `FieldParser` per field, grouped in
   `FAMILIES`) and `extractor.py` (`extract_pages` on page text, `extract_document` on a PDF).
   PR 6 adds a drug family and an allowance family to `FAMILIES` and their labels to
   `config.EXTRACT_LABELS`; nothing else needs to change.
2. **Finding a row.** A row is a text line that starts with the field's label (case-insensitive
   regex in `config.py`). The rest of the line is the cell; if it is empty, the next line is used.
   Labels are matched at the start of a line so "Prescription drug deductible" never reads as the
   medical deductible.
3. **Values.** "$1,500" and "$8,850.50" become exact decimals. Premium, deductible, and maximum
   out-of-pocket are money; every other cost-sharing field is a copay. "20% coinsurance" is always
   coinsurance, never a copay. "Not covered" has no unit. A unit phrase in the cell ("per day",
   "per year") beats the field's default unit.
4. **Two values in one cell** ("$0 or $40", "$40 out of network, $10 in network"): the part marked
   in network wins, else the first value. Confidence drops to 0.6 and a low-severity review item
   records the choice, so the pick is never silent.
5. **Inpatient stay** keeps the first day range only (as `docs/cms-fields.md` says for PBP):
   "$395 per day for days 1 to 5; $0 per day for days 6 to 90" is a $395 copay per day at full
   confidence. Without "days N" text, two amounts are treated as rule 4.
6. **Not found or unreadable.** The field is left out of the result (never a guess) and a
   `not_extracted` review item is added. Unreadable cells ("See your Evidence of Coverage") are
   cited; a field with no row at all has no evidence to cite, so its evidence list is empty.
7. **Different values on different pages.** The first page's value is kept with confidence 0.3,
   and a new review kind, `conflicting_values`, cites the first page of every distinct value. The
   same value repeated on later pages is not a conflict. Added to `ReviewKind` because none of the
   existing kinds fit.
8. **Only fields with a parser are reported missing.** Drug and allowance fields produce no
   review items until PR 6 adds their parsers.
9. **Citation snippet** is the cell text, cut to 120 characters (`Citation.text`).
10. **Unsure classification** still extracts; the review items then carry an empty plan id or
    year, as the classifier's own review item does.
11. **Factory:** `make_plan_pdf` gained `omit` and `extra_rows`; existing calls are unchanged.

No new dependencies.

## Risks and follow-ups

- Real SBs put labels and values in tables that pdfplumber may split across lines, and EOC prose
  can start a line with a label ("Emergency care is ..."). Lines with no readable value are only
  used when nothing else was found, but PR 15 must tune labels on real documents.
- "a month" or "a year" in a cell sets the unit; odd wording could pick a wrong unit.
- Allowance periods such as "per quarter" have no `Unit` yet; PR 6 decides.
