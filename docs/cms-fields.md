# Where each field lives in CMS public data

plan-diff checks every value it reads from a carrier PDF against CMS's official files (SPEC
section 6, step 6). This table says which CMS file and column holds each of the 15 v1 fields.

**Status: checked on 2026-10-05 (PR 15)** against the real PBP Benefits 2026 and 2027 files and
their data dictionaries (`PBP_Benefits_2026_dictionary.xlsx`, `PBP_Benefits_2027_dictionary.xlsx`),
the CY2026 and CY2027 Landscape (September 2026 release), and the 2027 Plan Crosswalk with its
readme. 2026 and 2027 use the same names for every column below. The layouts live in
`engine/src/plan_diff/cms/layouts.py` as data.

| Field | CMS file | Table and column | Notes |
|---|---|---|---|
| monthly_premium | Landscape (not in PBP) | `Monthly Consolidated Premium (Part C + D)` | PR 3 guessed "(Includes Part C + D)". A plan with no Part D says "Not Applicable" there; its premium is then `Part C Premium`, read only when `Part D Coverage Indicator` is No |
| medical_deductible | PBP | `pbp_Section_D.txt`, `pbp_d_inn_deduct_amt` | PR 3 guessed `pbp_d_ann_deduct_amt` (that is the out-of-network or PFFS deductible). `pbp_d_inn_deduct_yn` = 2 ("no in-network deductible") reads as $0 |
| moop_in_network | PBP | `pbp_Section_D.txt`, `pbp_d_out_pocket_amt` | confirmed |
| pcp_copay | PBP | `pbp_b7_health_prof.txt`, `pbp_b7a_copay_amt_mc_min` and `_max` | coinsurance in `pbp_b7a_coins_pct_mc_min` |
| specialist_copay | PBP | same table, `pbp_b7d_copay_amt_mc_min` and `_max` | coinsurance in `pbp_b7d_coins_pct_mc_min` |
| emergency_room | PBP | `pbp_b4_emerg_urgent.txt`, `pbp_b4a_copay_amt_mc_min` and `_max` | coinsurance in `pbp_b4a_coins_pct_mc_min` |
| urgent_care | PBP | same table, `pbp_b4b_copay_amt_mc_min` and `_max` | coinsurance in `pbp_b4b_coins_pct_mc_min` |
| inpatient_stay | PBP | `pbp_b1a_inpat_hosp.txt`, `pbp_b1a_copay_mcs_amt_int1_t1` | per day, first day range; coinsurance in `pbp_b1a_coins_mcs_pct_int1_t1` |
| outpatient_surgery | PBP | `pbp_b9_outpat_hosp.txt`, `pbp_b9a_copay_ohs_amt_min` and `_max` | PR 3 guessed file `pbp_b9a_outpat_hosp.txt`. CMS files one min and max for all Medicare-covered outpatient hospital services (9a1), so both real plans show a range ($0 to $100, $0 to $300, $0 to $200): never one value, "not comparable" |
| drug_deductible | PBP | `pbp_mrx.txt`, `mrx_alt_ded_amount` | confirmed. Empty for a plan with no Part D |
| drug_tier_1 to 3 | PBP | `pbp_mrx_tier.txt`, `mrx_tier_rstd_copay_1m` where `mrx_tier_id` = N | standard retail, 1 month; coinsurance in `mrx_tier_rstd_coins_1m` (Humana tier 3 is 17% in 2027) |
| dental_allowance | PBP | `pbp_b16_dental.txt`, `pbp_b16c_maxplan_cmp_amt`, period `pbp_b16c_maxplan_cmp_per` | PR 3 guessed `pbp_b16c_maxplan_amt` (no such column). When `pbp_b16c_maxplan_cmp_type` = 1 ("covered under 16b") the shared maximum is `pbp_b16b_maxplan_pv_amt`, period `pbp_b16b_maxplan_pv_per` |
| otc_allowance | PBP | `pbp_b13_other_services.txt`, `pbp_b13b_maxplan_amt`, period `pbp_b13b_otc_maxplan_per` | Both real plans leave 13b empty and file the OTC money in a Section D combined benefit group (`pbp_d_combo_nmc_cats_N` lists 13b; amount `pbp_d_combo_max_plan_ben_amt_N`, period `pbp_d_combo_max_plan_period_N`). The group name goes into the CMS citation. Wellcare's group also covers dental, vision, and hearing |

Period codes (same list in every "per" column): 1 every three years, 2 every two years, 3 every
year, 4 every six months, 5 every three months, 6 other, 7 every month. Codes 1, 2, and 6 have no
unit in the schema, so such a value is never compared.

Plan id: CMS splits it into contract (H0028), plan (030), and segment (000). The readers join them
as H0028-030, adding the segment (H0028-030-001) only when it is not 000. This rule lives in one
function, `normalize_plan_id` in `engine/src/plan_diff/models/ids.py`, which the classifier uses
too. H (local MA) and R (regional PPO) contracts are accepted; readers keep only the requested
plans, so S (Part D) and E (employer) rows are skipped.

## Crosswalk status labels

From the Part C and D Plan Crosswalk `STATUS` column (confirmed). The real 2027 file is a tab
separated text file (an Excel copy ships beside it) with no segment columns, so a crosswalk row
is plan level (segment 000). It writes NEW in the previous id columns of a new plan and TERMINATED
in the current id columns of an ended one. Each label maps onto the schema's CrosswalkStatus; any
other label stops the read with an error naming it.

| CMS label | CrosswalkStatus |
|---|---|
| New Plan | new |
| Renewal Plan | continuing |
| Consolidated Renewal Plan | consolidated (must name the current plan id) |
| Renewal Plan with SAR (service area reduction) | service_area_reduced |
| Renewal Plan with SAE (service area expansion) | service_area_expanded |
| Terminated/Non-renewed Plan, Terminated/Non-renewed Contract | terminated |
| Initial Contract (PR 15, seen in the real file: "a new plan under a new contract") | new |

Labels in the real 2027 file and their counts: Renewal Plan 4,899; New Plan 928; Consolidated
Renewal Plan 808; Renewal Plan with SAR 789; Renewal Plan with SAE 546; Initial Contract 168;
Terminated/Non-renewed Contract 1,006. "Terminated/Non-renewed Plan" does not appear in 2027 but
stays accepted. These match the PR 1 mapping and the readme's definitions.

Sources: 42 CFR 422.530 (https://www.law.cornell.edu/cfr/text/42/422.530) defines the renewal
options, and ResDAC (https://resdac.org/cms-data/variables/relationship-code) documents the
research version's codes N (new), R (renewal), C (consolidation), T (termination).

## Open questions (answered in PR 15)

1. Column names: checked; see the table. Corrections: Landscape premium and organization names,
   medical deductible column, outpatient table file name, dental and OTC columns.
2. The crosswalk ships as both a tab separated `.txt` and an `.xlsx`; the reader uses the text file.
3. PBP money columns are plain numbers ("3400.00"); the Landscape uses "$3,400.00 ". Both read.
4. Coinsurance and copay ranges are read (`AmountStatus.PERCENT`, `AmountStatus.RANGE`). A plan
   that files both a copay and a coinsurance for one service is `mixed` and stays "not in CMS".
5. OTC and dental periods are read from the CMS period codes. Inpatient later day ranges are still
   not read.
6. No duplicate PBP rows for the two Texas plans. The reader still stops rather than pick one.
