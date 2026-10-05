# Review 2 notes: extraction never guesses

Decisions made while fixing review 2 (subagent run, 2026-10-05). Rule: when a cell is unreadable or
ambiguous, the field is left unread or kept at lower confidence with a review item. Tests are in
`engine/tests/unit/test_review_2_extract.py`; constants are under `# Review 2` in `config.py`.

1. **F2, units by field.** Period words (monthly, a year, every quarter) set the unit only for the
   dental and OTC allowances. The premium is per month unless a period phrase sits right next to
   the premium amount ("$300 per year"). Every other field takes only per day, per stay, per
   admission, per visit, or per prescription, else its default unit. So "$3,400 (does not include
   your monthly premium)" is MOOP per year, and "$40 copay (annual limit...)" is a per visit copay.
   The PR 5 and PR 6 phrase table is split into `EXTRACT_COST_UNIT_PHRASES` and
   `EXTRACT_PERIOD_UNIT_PHRASES` (built from the old table, which is left as is).
2. **F4, wrapped values.** A label line with no value takes the next line only if that line does
   not start with any field label. Otherwise the field has an empty, unreadable hit.
3. **F5, unreadable beside readable.** Any unreadable row for a field plus a readable row is a
   `conflicting_values` review item at confidence 0.3 that cites both. The readable value is kept
   at that low confidence. This replaces the PR 5 behavior of quietly ignoring unreadable rows.
4. **F5, sections.** A heading is a whole line with no `$`, `%`, or digit that is not a field
   label. A drug heading ("Prescription drug benefits", "Part D drug coverage", "Pharmacy") starts
   a drug section; a medical heading ("Medical benefits", "Hospital", "Dental", "Other") ends it.
   The section carries across pages. Inside a drug section the medical deductible label must say
   "medical" or "health", so a bare "Deductible $250" is never the medical deductible. It is not
   read as the drug deductible either (that would be a guess); it is simply skipped.
5. **F8, not covered first.** "Not covered" is a value like an amount. A 100% next to it only
   restates it, so "Not covered (you pay 100%)" is NotCovered. "$40 copay; not covered" is two
   values and goes through the usual two-value rule (confidence 0.6 and a review item).
6. **F9, inpatient.** The in-network rule runs before the day-range rule, and any day range in the
   chosen value's segment (or the whole cell when no marker picked) makes the unit per day. An
   ellipsis or a sentence end now also splits a cell into segments.
7. **F10, the value's own words.** The unit is read only from the chosen value's span: its segment,
   cut at neighbouring values and at any parenthesis. "$50 ($200 a year)" for an allowance is $50
   with no unit and an `unknown_period` review item. An allowance with no period next to its
   amount ("$1,500", "$0") also gets no unit and that review item, never per year. The PR 6 test
   that expected "$0" dental to be per year now expects no unit.
8. **F11, footnotes.** Superscript digits, `*`, and daggers are stripped before reading. A digit
   glued to the amount ("$1,5001", "$45.501") or one or two lone digits after it ("$45 1") may be
   a footnote or part of the number: the amount without it is kept at confidence 0.6 with a
   `conflicting_values` review item (no new review kind, so the schema is unchanged).

9. **Labeled picks (coordinator follow-up).** The diff fix sets a 0.7 confidence floor for the
   shop-again flag, so 0.6 on every two-value cell would leave most real plans undecided. When
   the chosen value's own words (its segment, between its neighbouring values) carry an explicit
   in-network or standard pharmacy marker, it is read at 0.85 with a low-severity
   `conflicting_values` item that says "explicitly labeled". A "first value" pick, or a marker
   that is not next to the chosen value, stays at 0.6. The 30-day supply rule alone is not on
   the trusted list (`EXTRACT_LABELED_RULES`). PR 5 and PR 6 tests now expect 0.85 for labeled
   cells and still expect 0.6 for "$0 or $40".
10. **Merge.** main added its own `# Review 2` block (diff) to `config.py`; this fix's constants
    follow under `# Review 2 (extraction)`. No other section moved.

11. **Unexpected unit (coordinator follow-up 2).** A MOOP or medical or drug deductible whose own
    words state a non-yearly period ("$3,400 per month") keeps the amount and the stated unit at
    confidence 0.5 (below the 0.7 shop-again floor) with a new review kind `unexpected_unit`.
12. **Attached periods.** For allowances and the premium, a period right after the chosen value
    inside a parenthesis or after a comma ("$1,500 (per year)", "$50, every quarter") is that
    value's own period. A parenthesis that starts with another value ("$50 ($200 a year)") is not.

## Risks and follow-ups

- Section headings are a phrase list; real SBs may title sections differently. PR 15 must check.
- Allowance cells that put the period in a separate column now go to review instead of being
  read. That is safe but adds review volume.
- Treating an unreadable row as a conflict will lower confidence wherever EOC prose starts a line
  with a field label. Safe direction, but expect more review items on long documents.
