# Canonical plan schema

Every model lives in `engine/src/plan_diff/models/`. All models refuse unknown fields and cannot be
changed after they are made. Money is always an exact decimal with 2 places, never a float.
`plan-diff schema export --out <folder>` writes one JSON Schema file per run output model.

## Shared building blocks

| Name | What it holds | Rules |
|---|---|---|
| PlanId | Medicare contract-plan id | `H` plus 4 digits, dash, 3 digits; optional `-` plus 3-digit segment. Example H0028-030 |
| PlanYear | Plan year | Whole number, 2006 to 2100 |
| Carrier | Carrier name | Any text; extra spaces are collapsed |
| DocumentType | Kind of carrier document | SB (Summary of Benefits), EOC (Evidence of Coverage), ANOC (Annual Notice of Change), OTHER |
| Citation | Where a value came from | document id, page (starts at 1), method (rule, llm, cms, human), optional snippet up to 200 characters. For method cms, page is the row number in the CMS file |

## The 15 fields (SPEC decision 3)

| Field | Change category | Usual value and unit |
|---|---|---|
| monthly_premium | premium | money, per month |
| medical_deductible | deductible | money, per year |
| moop_in_network | moop | money, per year (maximum out-of-pocket, in network) |
| pcp_copay | copays | copay or coinsurance, per visit |
| specialist_copay | copays | copay or coinsurance, per visit |
| emergency_room | copays | copay or coinsurance, per visit |
| urgent_care | copays | copay or coinsurance, per visit |
| inpatient_stay | copays | copay per day or per stay, or coinsurance |
| outpatient_surgery | copays | copay or coinsurance, per visit |
| drug_deductible | drugs | money, per year |
| drug_tier_1 | drugs | copay or coinsurance, per prescription |
| drug_tier_2 | drugs | copay or coinsurance, per prescription |
| drug_tier_3 | drugs | copay or coinsurance, per prescription |
| dental_allowance | allowances | money, per year, or not covered |
| otc_allowance | allowances | money, per month, per quarter, or per year, or not covered |

A value is one of: **money** (an amount), **copay** (a fixed amount per unit), **coinsurance** (a
percent, 0 to 100), or **not covered**. An ExtractedField adds the unit, the citation, and a
confidence score from 0 to 1. `annualize(amount, unit)` turns a per-month, per-quarter, or
per-year amount into a yearly one, so allowances with different periods compare fairly.

## Run output models

| Model | Run file | Key fields |
|---|---|---|
| SourcesManifest | `sources/manifest.json` | list of SourceDocument: id, url, sha256 (empty until first fetch), size, retrieved date, carrier, plan (empty for CMS files), year, document type, landing page, verified, note. Ids must be unique; a pinned file must have size and date; a document with no url needs a note. See docs/sources.md |
| PlanRecord | `plans/<plan>_<year>.json` | plan id, year, carrier, plan name, counties, fields by name, document ids. A PDF citation must point at a listed document |
| ValidationResult | `validation.json` | field, PDF value, CMS value, verdict (match, mismatch, not_comparable, not_in_cms, not_extracted), PDF page and CMS row citations |
| PlanDiff | `diff/<plan>.json` | old and new plan id, years, crosswalk status, changes, shop_again, reasons, evidence (the crosswalk row), review. Shop again is on exactly when there are reasons; it is empty (undecided) when the crosswalk row is missing, or when no reason fires but a deciding field is uncertain (Review 2), always with a high review item. It is never off while a shop_again_uncertain item is open |
| ReviewItem | `review_queue.jsonl` | kind, plan, year, field, evidence citations, reason, severity (low, medium, high) |

A FieldChange holds the old and new ExtractedField (so both pages travel with the change), the
change category, and a direction: up, down, same, added, removed, or not_comparable (a different
kind of value, for example a copay that became coinsurance, an allowance with no period, or a field
absent in either year, which goes to review). Removed needs an explicit not covered value this year;
added needs an explicit not covered value last year.

## Crosswalk status

| Status | CMS crosswalk label | Needs old id | Needs new id |
|---|---|---|---|
| new | New Plan | no | yes |
| continuing | Renewal Plan | yes | yes |
| consolidated | Consolidated Renewal Plan | yes | yes |
| service_area_reduced | Renewal Plan with SAR | yes | yes |
| service_area_expanded | Renewal Plan with SAE | yes | yes |
| terminated | Terminated/Non-renewed plan or contract | yes | no |

Labels come from CMS guidance and 42 CFR 422.530 (see the research file, section 1c). They are not
yet confirmed against the crosswalk file's own codebook; PR 3 confirms them. An unknown label is an
error, never a guess.

## Validation (PR 7)

ValidationResult also carries the unit on each side and, for a mismatch, the reason. Allowances
compare as yearly amounts, and only when both sides name a period. AccuracyTable (`accuracy.json`)
has one row per field and extraction method plus a total per method: matched, mismatched, not
extracted, not in CMS, and the match rate over fields that could be compared. A ReviewItem may
carry a confidence from 0 to 1.

Release 0.1.0: when the two sides state different periods or units ("period not comparable",
"unit not comparable") the verdict is `not_comparable`, not `mismatch`. It is counted in its own
`not_comparable` column, left out of the match rate, and still goes to review (kind
`not_comparable`, medium). AccuracyTable also names its slice: `plans`, `years`, `run_id`, and
`as_of` (the run's start date).
