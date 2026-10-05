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
| otc_allowance | allowances | money, per month or per year, or not covered |

A value is one of: **money** (an amount), **copay** (a fixed amount per unit), **coinsurance** (a
percent, 0 to 100), or **not covered**. An ExtractedField adds the unit, the citation, and a
confidence score from 0 to 1.

## Run output models

| Model | Run file | Key fields |
|---|---|---|
| SourcesManifest | `sources/manifest.json` | list of SourceDocument: id, url, sha256 (empty until first fetch), size, retrieved date, carrier, plan, year, document type. Ids must be unique; a pinned file must have size and date |
| PlanRecord | `plans/<plan>_<year>.json` | plan id, year, carrier, plan name, counties, fields by name, document ids. A PDF citation must point at a listed document |
| ValidationResult | `validation.json` | field, PDF value, CMS value, verdict (match, mismatch, not_in_cms, not_extracted), PDF page and CMS row citations |
| PlanDiff | `diff/<plan>.json` | old and new plan id, years, crosswalk status, changes, shop_again, reasons. Shop again is on exactly when there are reasons |
| ReviewItem | `review_queue.jsonl` | kind, plan, year, field, evidence citations, reason, severity (low, medium, high) |

A FieldChange holds the old and new ExtractedField (so both pages travel with the change), the
change category, and a direction: increased, decreased, added, removed, or changed (a different
kind of value, for example a copay that became coinsurance).

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
