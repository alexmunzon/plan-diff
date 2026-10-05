# PR 15 notes: first run on real Texas documents

Decisions made while building, without questions to Alex (subagent run, 2026-10-05). Branch
`pr-15-real-fetch`, local only. Nothing was downloaded in this session: every file came from the
17 already pinned in `sources/manifest.json` (commit db2052e). Jev and the LLM stayed off.

## What was run

    cd engine
    uv run plan-diff unzip-cms --raw ../data/raw
    uv run plan-diff run --docs ../data/raw/docs-texas --cms ../data/raw/cms-texas \
      --plans H0028-030,H5294-014 --years 2026,2027 --data-kind public \
      --sources ../sources/manifest.json --out ../runs --run-id texas-2026-2027 \
      --now 2026-10-05T12:00:00Z

Two folders under the git-ignored `data/raw/` hold symlinks only:
- `cms-texas/` maps the run's names to the real files: `landscape_2026.csv` and
  `landscape_2027.csv` (the Landscape CSVs), `pbp_2026/` and `pbp_2027/` (the unzipped PBP folders),
  `crosswalk_2027.csv` (`PlanCrosswalk2027_10012026.txt`, tab separated).
- `docs-texas/` holds the 12 carrier PDFs. **Deviation from the brief:** `--docs ../data/raw` would
  also pick up `2027_plan_crosswalk_readme.pdf`, which ships inside the crosswalk zip, and would
  send it to review as an unknown document. Pointing `--docs` at the 12 carrier PDFs avoids that.

The outputs (JSON and JSONL only, no parquet, no PDF) are committed in
`dashboard/public/texas-run/`. Two runs give byte-identical files (frozen clock).

## Facts that differed from the brief

1. **The 2026 Wellcare Summary of Benefits is not a multi-plan booklet.** The pinned file (24
   pages) names only Wellcare Patriot Simple (HMO): page 1 says "H5294 | 014 | 000" and pages 4 to
   16 carry the header "H5294, Plan 014, 000". Pages 17 to 24 are language notices, a checklist, and
   blank pages. No other plan id appears. The "H5294-202" seen earlier is almost certainly the file
   code "H5294_2026_TX_SB..." read as plan 202; the classifier now refuses that reading (a plan
   number must not be followed by a digit) and a test pins it.
2. A fourth id form exists: "H5294 | 014 | 000" (SB page 1), besides "H5294_014" (file codes in the
   EOC and ANOC) and "H5294, Plan 014, 000" (SB page headers).

## CMS layout corrections (data in `cms/layouts.py`, details in `docs/cms-fields.md`)

| What | PR 3 guess | Real 2026 and 2027 |
|---|---|---|
| Crosswalk format | comma, with segment columns | tab separated `.txt`, no segment columns (plan level), NEW and TERMINATED written in empty id columns |
| Crosswalk label | | "Initial Contract" (168 rows) is new: mapped to `new` per the readme |
| Landscape premium | `Monthly Consolidated Premium (Includes Part C + D)` | `Monthly Consolidated Premium (Part C + D)` |
| Landscape organization | `Organization Name` | `Organization Marketing Name` |
| No-Part-D premium | | "Not Applicable"; read `Part C Premium` when `Part D Coverage Indicator` is No (Wellcare) |
| Medical deductible | `pbp_d_ann_deduct_amt` | `pbp_d_inn_deduct_amt`; `pbp_d_inn_deduct_yn` = 2 means $0 |
| Outpatient file | `pbp_b9a_outpat_hosp.txt` | `pbp_b9_outpat_hosp.txt` |
| Dental | `pbp_b16c_maxplan_amt` | `pbp_b16c_maxplan_cmp_amt` + `_per`; 16b shared maximum when 16c type is 1 (Humana) |
| OTC | `pbp_b13b_maxplan_amt` | same column plus `pbp_b13b_otc_maxplan_per`, but both plans leave it empty; the money is in a Section D combined group that lists 13b |

Every other guessed column was right. New reader rules: a min and max that differ are a **range**
(never one value; verdict "not comparable", reason "CMS gives a range"); no copay but a coinsurance
percent is a **coinsurance** (Humana tier 3 in 2027 is 17%); both is **mixed** (not in CMS). The
CMS period codes give dental and OTC a unit, so those fields now compare instead of always showing
"period not comparable". `ValidationResult` gains `cms_max` (optional; old JSON loads). The
synthetic fixtures in `fixtures/cms/` moved to the real shapes with no value changes; the demo was
regenerated (only `manifest.json` hashes, `plan_pages`, and `cms_max` lines changed).

## Classifier and booklets

- `normalize_plan_id` and `config.PLAN_ID_PATTERN` accept "H5294_014", "H5294 | 014 | 000", and
  "H5294, Plan 014, 000". All 12 real PDFs now classify SURE (before: the 6 Wellcare ones were unsure).
- Booklets (`classify/booklet.py`): a page that names exactly one plan belongs to it, and the pages
  after it until another plan is named; a page naming two or more plans belongs to nobody. With
  `plan_name`, a page that prints the requested plan's name counts too. The requested plan's pages
  must be one range, else the document goes to review (`unclassified_document`, reason says why).
  Pages outside the range are blanked, so page numbers stay real; each citation from a booklet starts
  "booklet pages A to B for PLAN:" and the run manifest's input gets `plan_pages`. None of the 12
  real documents is a booklet, so this is tested on synthetic page text only.
- The run now opens each PDF once and extracts all pages' text once (classify reads the first 3).

## Extraction tuning (config `# PR 15`, tests in `test_pr_15_extract.py` on real snippets)

- New and tightened row labels: the premium label skips "Monthly Premium, Deductible and Limits"
  (a heading); MOOP accepts "Medical Maximum out-of-pocket" and "(MOOP)"; PCP and specialist accept
  "Primary Care Provider (PCP) •" and "Specialists $"; "Urgently Needed Services $"; "Pharmacy (Part D)
  deductible". MOOP and emergency labels count only when a value follows (an amount, an in- or
  out-of-network marker, or the line end), so "emergency care you received" and "maximum
  out-of-pocket amount." in sentences are not rows.
- A deductible cell that names a drug tier, Part D, or drugs is never the medical deductible.
  "No deductible" and "does not have a deductible" read as $0.
- **Tier split drug deductible**: "$0 deductible for Tier 1, Tier 2 and Tier 3" plus "$615 deductible
  for Tier 4 and Tier 5" on the next line reads $615, the highest tier amount, at 0.85 with a low
  review item naming the rule. This is how CMS files it (`mrx_alt_ded_amount` $615 plus the exempt
  tiers), and both years matched CMS.
- Section rows (rows that only mean something inside one section): Humana urgent care center,
  outpatient hospital "Surgery services", the Humana dental "$4,000 maximum benefit coverage amount
  per / year", the Wellcare "up to $3,000 per plan year", the Humana "$75 quarterly allowance", and
  the Wellcare Spendables "$50 monthly". A section ends at the next ALL CAPS heading or after a set
  number of lines. The insulin price table is skipped (it repeats the tier labels).
- Continuations: a row ending in ":" takes the bullet lines under it (Wellcare inpatient); a cell
  ending in "per" takes the next line.
- A label line with no value whose next line also has no value is now a heading, not an unreadable
  row (Humana "Over-the-Counter (OTC) Allowance" above "Humana Well Dine Meal Program"). Before, it
  lowered the real value's confidence to 0.3.
- A line ending in "." is no longer a section heading ("Additional details below." had switched the
  drug section off).
- **ANOC rows with two or more values are never read**: an ANOC prints last year and next year side
  by side, so the first value is last year's. Before this rule the 2026 Humana ANOC gave $75 inpatient
  (the 2025 value) and the 2026 Wellcare ANOC gave $150 outpatient surgery (an ambulatory surgery
  center value from 2025). Both were caught before commit.
- En and em dashes in carrier text become hyphens before extraction, so no quoted snippet carries
  one. One test string keeps the real en dash as a `–` escape.
- Drug tiers in Humana's grid stay at 0.6 ("took the first value"): the first column is retail
  30-day, which is what CMS files, but the rule does not read the grid header, so it is not trusted.

## Results (Texas slice, H0028-030 and H5294-014, 2026 vs 2027, as of 2026-10-05)

| Plan | Shop again | Reasons | Crosswalk |
|---|---|---|---|
| Humana Gold Plus H0028-030 | Yes | drug deductible up $85 ($615 to $700); also seen, below threshold: MOOP $3,400 to $3,900, specialist $15 to $20, inpatient $95 to $150 a day, outpatient surgery $100 to $300, OTC $75 to $60 a quarter, tier 3 $45 copay to 17% coinsurance (not comparable) | Renewal Plan |
| Wellcare Patriot Simple H5294-014 | Yes | service area lost 33 of 84 counties (CMS "Renewal Plan with SAR") | Renewal Plan with SAR |

Accuracy (method rule, 60 values = 2 plans x 2 years x 15 fields):

| Matched | Mismatched | Not comparable | Not extracted | Not in CMS | Match rate |
|---|---|---|---|---|---|
| 48 | 0 | 2 | 10 | 0 | 100% (48 of 48) |

- Not comparable (2): Humana outpatient surgery both years; CMS files a range ($0 to $100, $0 to $300).
- Not extracted (10): Wellcare outpatient surgery both years (the SB has no surgery row, only
  "Outpatient Hospital Services $0 ... $200 for all other"); Wellcare drug deductible and tiers 1 to
  3 both years (the plan has no Part D: "Plan does not cover Part D."; CMS agrees, its drug columns
  are empty).
- Review queue (23): high 1 `shop_again_uncertain` (Wellcare drug deductible missing both years;
  the flag is still yes from the service area loss); medium 10 `not_extracted`, 2 `not_comparable`;
  low 10 `conflicting_values` (6 drug tier grid picks, 2 tier split deductibles, 2 from the Humana EOC).

**Read these numbers with care.** The rules were tuned on these same four Summary of Benefits files,
so 100% is a fit to the training documents, not a measured accuracy. There is no held-out document.

## Hand check (SB pages the run cites, rendered to images and read by eye)

| Plan, year | Field | Extracted | Page | What the page says | OK |
|---|---|---|---|---|---|
| H0028-030 2026 | premium | $0 a month | 4 | "Monthly plan premium $0" | yes |
| H0028-030 2026 | MOOP | $3,400 a year | 4 | "Medical Maximum out-of-pocket responsibility $3,400 in-network" | yes |
| H0028-030 2026 | PCP | $0 a visit | 4 | "Primary Care Provider (PCP): PCP's office: $0 copay" | yes |
| H0028-030 2026 | specialist | $15 a visit | 4 | "Specialist: Specialist's office: $15 copay" | yes |
| H0028-030 2026 | drug deductible | $615 a year | 4 | "Pharmacy (Part D) deductible: $0 deductible for Tier 1, Tier 2 and Tier 3; $615 deductible for Tier 4 and Tier 5" | yes (highest tier amount, as CMS files it) |
| H0028-030 2027 | premium | $0 a month | 4 | "Monthly plan premium $0" | yes |
| H0028-030 2027 | MOOP | $3,900 a year | 4 | "$3,900 in-network" | yes |
| H0028-030 2027 | PCP | $0 a visit | 4 | "PCP's office: $0 copay" | yes |
| H0028-030 2027 | specialist | $20 a visit | 4 | "Specialist's office: $20 copay" | yes |
| H0028-030 2027 | drug deductible | $700 a year | 4 | "$0 deductible for Tier 1, Tier 2 and Tier 3; $700 deductible for Tier 4 and Tier 5" | yes (same rule) |
| H5294-014 2026 | premium | $0 a month | 4 | "Monthly Plan Premium $0" | yes |
| H5294-014 2026 | MOOP | $3,400 a year | 4 | "Maximum Out-of-Pocket (MOOP) Responsibility $3,400 annually" | yes |
| H5294-014 2026 | PCP | $0 a visit | 4 | "Doctor Visits, Primary Care Providers $0 copay" | yes |
| H5294-014 2026 | specialist | $10 a visit | 5 | "Specialists $10 copay" | yes |
| H5294-014 2026 | drug deductible | not extracted | 4 | "Plan does not cover Part D." | correct to leave it out |
| H5294-014 2027 | premium | $0 a month | 4 | "Monthly Plan Premium $0" | yes |
| H5294-014 2027 | MOOP | $3,400 a year | 4 | "$3,400 annually" | yes |
| H5294-014 2027 | PCP | $0 a visit | 5 | "Primary Care Providers $0 copay" | yes |
| H5294-014 2027 | specialist | $10 a visit | 5 | "Specialists $10 copay" | yes |
| H5294-014 2027 | drug deductible | not extracted | 4 | "Plan does not cover Part D." | correct to leave it out |

18 cited values checked by eye, 0 wrong; 2 "not extracted" confirmed as no Part D. No mismatch found.

## Dashboard

A second route, not a client-side switcher: `/texas` (Overview), `/texas/plans`,
`/texas/plans/[plan]`, `/texas/changes`, `/texas/trust`, `/texas/documents`, all static and read at
build time from `public/texas-run/`. The demo stays the default at `/`. The nav shows two run links
("Demo run (synthetic)", "Texas 2026 to 2027 (public)") and the page links follow the run you are in.
Chosen over a query parameter because every page stays static and each run has its own URL to share.
Carrier citations link to the pinned https URL plus `#page=N`; no PDF is served.

## Risks and follow-ups

- **Over-fit**: rules were written against these four SBs. A new carrier layout will mostly give
  "not extracted" (safe), but section rows and labels are carrier specific. Next real plan should be
  run before any tuning to get an honest accuracy number.
- Wellcare's drug fields will always be "not extracted" and leave a high review item: the run does
  not yet read "Plan does not cover Part D" or the Landscape's Part D indicator as "no drug coverage".
- Outpatient surgery can never be checked against CMS while CMS files one range for all outpatient
  hospital services.
- The Wellcare OTC value is a shared card (OTC, dental, vision, hearing); CMS files it the same way,
  so it matches, but a broker should not read it as OTC only. The CMS citation names the group.
- The EOCs still produce prose hits (low items) and the ANOCs are now mostly unread. Both are below
  the SB in precedence, so they only add review items.
- The run manifest lists all 301 CMS files (whole PBP folders), about 125 KB.
- Size: about 880 engine source lines, 560 test lines, and 300 dashboard lines changed, plus
  fixtures and run JSON; far over the 400 line target. The brief's scope did not split cleanly.
