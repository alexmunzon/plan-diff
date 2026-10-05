# PR 6 notes: deterministic extraction, drug and allowance fields

Decisions made while building, without questions to Alex (subagent run, 2026-10-05).

1. **Two new families.** `DRUGS` (drug deductible, tiers 1 to 3) and `ALLOWANCES` (dental, OTC)
   sit beside `COST_SHARING` in `FAMILIES`. All 15 v1 fields now have exactly one parser, so a
   field missing from any document now becomes a `not_extracted` review item.
2. **Labels** (in `config.py` under `# PR 6`, added to the PR 5 table). The drug deductible needs a
   drug word ("Prescription drug", "Part D", "Rx drug", "Pharmacy") so a bare "Deductible" row stays
   the medical deductible. A tier label is "Tier N", optionally followed by its group ("(preferred
   generic)", "preferred brand drugs"); "Tier 1" never matches "Tier 10". Dental and OTC labels
   need an allowance word (allowance, maximum, limit; allowance, credit, card), so a "Preventive
   dental $0 copay" row is not read as the allowance.
3. **Drug tiers** mean the standard retail, 30-day supply price in the initial coverage stage.
   Values are a copay or coinsurance per prescription; "Not covered" has no unit.
4. **Preferred vs standard pharmacy.** PR 5's in-network rule is now a list of preferred markers
   per field (`config.EXTRACT_PREFER_MARKERS`): in-network, then standard pharmacy, then 30-day
   supply for drug tiers; in-network only for every other field. "$47 copay (standard) / $42
   (preferred)" reads $47. Like PR 5's two-value rule, the pick is never silent: confidence 0.6
   and a low-severity `conflicting_values` review item that names the rule ("took the standard
   pharmacy value"). No marker at all still takes the first value and says "first".
5. **Unit decision.** Added `Unit.PER_QUARTER` (`PER_MONTH` already existed). Allowances keep the
   period the document states ("$50 every quarter" is $50 per quarter), so the citation matches
   the page; the diff compares yearly amounts through `annualize(value, unit)`, a pure helper in
   `models/fields.py` that returns a Decimal (month x12, quarter x4, year x1), refuses floats, and
   refuses units that are not a period (per visit, per day). Quarter phrases: per, a, every, each
   quarter, quarterly, every 3 months. An allowance with no period defaults to per year.
6. **Small fix to the PR 5 splitter.** A comma inside an amount ("$1,500") no longer splits a cell
   into two values.
7. **PR 5 test updated**, not weakened: SPEC example 1 now expects all 15 fields, and the drug
   deductible test also checks the drug value is read.

No new dependencies.

## Risks and follow-ups

- Real SBs often list tiers in a grid (preferred, standard, mail order; 30, 60, 90 days) that
  pdfplumber may flatten into one line with many amounts. The marker rules handle labeled cells;
  an unlabeled grid takes the first amount at 0.6 confidence and goes to review. PR 15 must check.
- Deductible-stage vs initial-coverage-stage wording is not read yet; a tier row inside a
  deductible-stage table would be taken as is.
- An OTC allowance with an unusual period ("every 6 months") falls back to per year. Review it on
  real documents.
