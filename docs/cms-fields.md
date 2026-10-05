# Where each field lives in CMS public data

plan-diff checks every value it reads from a carrier PDF against CMS's official files (SPEC
section 6, step 6). This table says which CMS file and column holds each of the 15 v1 fields.

**Status: unconfirmed.** The column names below follow the names CMS has used in past PBP,
Landscape, and Crosswalk releases. The 2026 and 2027 data dictionaries ship inside the ZIP files,
and the CMS web pages do not list columns, so the names get checked the day the real files arrive.
If a name is wrong, the fix is one line in `engine/src/plan_diff/cms/layouts.py`, not new code.

Terms, once: **PBP** is CMS's file of every Medicare Advantage plan's filed benefits, split into
tab-separated tables by section. The **Landscape** is one row per plan per county with the premium.

| Field | CMS file | Table and column | Notes |
|---|---|---|---|
| monthly_premium | Landscape (not in PBP) | `Monthly Consolidated Premium (Includes Part C + D)` | PBP Section D holds only the Part C piece, so the Landscape is the reference |
| medical_deductible | PBP | `pbp_Section_D.txt`, `pbp_d_ann_deduct_amt` | |
| moop_in_network | PBP | `pbp_Section_D.txt`, `pbp_d_out_pocket_amt` | |
| pcp_copay | PBP | `pbp_b7_health_prof.txt`, `pbp_b7a_copay_amt_mc_min` | Copay only; coinsurance plans not read yet |
| specialist_copay | PBP | `pbp_b7_health_prof.txt`, `pbp_b7d_copay_amt_mc_min` | Same |
| emergency_room | PBP | `pbp_b4_emerg_urgent.txt`, `pbp_b4a_copay_amt_mc_min` | |
| urgent_care | PBP | `pbp_b4_emerg_urgent.txt`, `pbp_b4b_copay_amt_mc_min` | |
| inpatient_stay | PBP | `pbp_b1a_inpat_hosp.txt`, `pbp_b1a_copay_mcs_amt_int1_t1` | Per day, first day range only |
| outpatient_surgery | PBP | `pbp_b9a_outpat_hosp.txt`, `pbp_b9a_copay_ohs_amt_min` | Hospital outpatient; surgery centers are a separate table (b9b) |
| drug_deductible | PBP | `pbp_mrx.txt`, `mrx_alt_ded_amount` | |
| drug_tier_1 | PBP | `pbp_mrx_tier.txt`, `mrx_tier_rstd_copay_1m` where `mrx_tier_id` = 1 | Standard retail, 1 month supply |
| drug_tier_2 | PBP | same, tier 2 | |
| drug_tier_3 | PBP | same, tier 3 | |
| dental_allowance | PBP | `pbp_b16_dental.txt`, `pbp_b16c_maxplan_amt` | Comprehensive dental maximum |
| otc_allowance | PBP | `pbp_b13_other_services.txt`, `pbp_b13b_maxplan_amt` | Period (month, quarter, year) not read yet |

Plan id: CMS splits it into contract (H0028), plan (030), and segment (000). The readers join them
as H0028-030, adding the segment (H0028-030-001) only when it is not 000.

## Crosswalk status labels

From the Part C and D Plan Crosswalk `STATUS` column (assumed name). Each label maps onto the
schema's CrosswalkStatus; any other label stops the read with an error naming it.

| CMS label | CrosswalkStatus |
|---|---|
| New Plan | new |
| Renewal Plan | continuing |
| Consolidated Renewal Plan | consolidated (must name the current plan id) |
| Renewal Plan with SAR (service area reduction) | service_area_reduced |
| Renewal Plan with SAE (service area expansion) | service_area_expanded |
| Terminated/Non-renewed Plan, Terminated/Non-renewed Contract | terminated |

Sources: 42 CFR 422.530 (https://www.law.cornell.edu/cfr/text/42/422.530) defines the renewal
options, and ResDAC (https://resdac.org/cms-data/variables/relationship-code) documents the
research version's codes N (new), R (renewal), C (consolidation), T (termination).

## Open questions (answer when the real files arrive)

1. Exact column names and labels in each 2026 and 2027 file, against the data dictionary in each ZIP.
2. Whether the Crosswalk ZIP holds a CSV, a tab-separated text file, or an Excel file.
3. Whether PBP money columns hold plain numbers or formatted text (the reader accepts both).
4. Plans that charge coinsurance instead of a copay (separate `coins_pct` columns), and copays that
   differ by tier of provider. v1 reads the copay amount only; a missing copay reads as empty.
5. Inpatient cost sharing by day range, and OTC allowance period, need extra columns.
6. Whether any PBP table has more than one row per plan. The reader stops rather than pick one.
