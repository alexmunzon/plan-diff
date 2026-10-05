"""Per-year column layouts for CMS public files. A layout change between years is data, not code.

PR 15: every name below was checked against the real 2026 and 2027 files (PBP Benefits 2026 and
2027 with their data dictionaries, CY2026 and CY2027 Landscape 202609, PlanCrosswalk2027_10012026)
on 2026-10-05. docs/cms-fields.md lists what changed from the PR 3 guesses.
"""

from dataclasses import dataclass, field

from plan_diff.models import FieldName


@dataclass(frozen=True)
class CrosswalkLayout:
    # PR 15: the real crosswalk is tab separated and has no segment columns (plan level only).
    separator: str = "\t"
    previous_contract: str = "PREVIOUS_CONTRACT_ID"
    previous_plan: str = "PREVIOUS_PLAN_ID"
    previous_segment: str | None = None
    current_contract: str = "CURRENT_CONTRACT_ID"
    current_plan: str = "CURRENT_PLAN_ID"
    current_segment: str | None = None
    status: str = "STATUS"


@dataclass(frozen=True)
class LandscapeLayout:
    separator: str = ","
    contract: str = "Contract ID"
    plan: str = "Plan ID"
    segment: str = "Segment ID"
    organization: str = "Organization Marketing Name"
    plan_name: str = "Plan Name"
    state: str = "State Territory Name"
    county: str = "County Name"
    premium: str = "Monthly Consolidated Premium (Part C + D)"
    # PR 15: a plan without Part D has "Not Applicable" as its consolidated premium. Its whole
    # premium is then the Part C premium, read only when the Part D indicator says No.
    part_c_premium: str = "Part C Premium"
    part_d_indicator: str = "Part D Coverage Indicator"


# PR 15: CMS period codes (PBP data dictionary, the same list for every "per" column).
# 1 every three years, 2 every two years, and 6 other have no Unit, so they are never compared.
PBP_PERIOD_CODES: dict[str, str] = {
    "3": "per_year",
    "4": "per_half_year",
    "5": "per_quarter",
    "7": "per_month",
}


@dataclass(frozen=True)
class PbpColumn:
    """Where one field lives in the PBP: a table file, a column, and for tiered tables a tier id.

    PR 15 (all optional, read from the real files): `max_column` is the top of a range (a range
    with different ends is never one value), `coins_column` a coinsurance percent read when there
    is no copay, `period_column` the CMS period code of an allowance, `zero_when` a (column, code)
    answer that means $0 (for example "no in-network deductible"), `combo_category` a category
    looked up in the Section D combined benefit groups, `fallback` a second place to look, and
    `only_when` a (column, code) answer this place needs before it is read at all."""

    file: str
    column: str
    tier: str | None = None
    max_column: str | None = None
    coins_column: str | None = None
    coins_max_column: str | None = None
    period_column: str | None = None
    zero_when: tuple[str, str] | None = None
    combo_category: str | None = None
    fallback: "PbpColumn | None" = None
    only_when: tuple[str, str] | None = None


def _copay(file: str, prefix: str, coins: str) -> PbpColumn:
    return PbpColumn(
        file,
        f"{prefix}_min",
        max_column=f"{prefix}_max",
        coins_column=coins,
        coins_max_column=coins.removesuffix("_min") + "_max",
    )


_SECTION_D = "pbp_Section_D.txt"
_PROF = "pbp_b7_health_prof.txt"
_ER = "pbp_b4_emerg_urgent.txt"
_TIER = "pbp_mrx_tier.txt"
_DENTAL = "pbp_b16_dental.txt"

# Section D combined supplemental benefit groups: up to this many numbered groups per plan.
PBP_COMBO_GROUPS = 9
PBP_COMBO_COLUMNS = {
    "categories": "pbp_d_combo_nmc_cats_{n}",
    "amount": "pbp_d_combo_max_plan_ben_amt_{n}",
    "period": "pbp_d_combo_max_plan_period_{n}",
    "name": "pbp_d_combo_grp_name_{n}",
}

_PBP_2026_FIELDS: dict[FieldName, PbpColumn | None] = {
    # Not read from PBP: Section D holds only the Part C piece. The Landscape holds the
    # consolidated Part C + D premium that a Summary of Benefits quotes.
    FieldName.MONTHLY_PREMIUM: None,
    FieldName.MEDICAL_DEDUCTIBLE: PbpColumn(
        _SECTION_D, "pbp_d_inn_deduct_amt", zero_when=("pbp_d_inn_deduct_yn", "2")
    ),
    FieldName.MOOP_IN_NETWORK: PbpColumn(_SECTION_D, "pbp_d_out_pocket_amt"),
    FieldName.PCP_COPAY: _copay(_PROF, "pbp_b7a_copay_amt_mc", "pbp_b7a_coins_pct_mc_min"),
    FieldName.SPECIALIST_COPAY: _copay(_PROF, "pbp_b7d_copay_amt_mc", "pbp_b7d_coins_pct_mc_min"),
    FieldName.EMERGENCY_ROOM: _copay(_ER, "pbp_b4a_copay_amt_mc", "pbp_b4a_coins_pct_mc_min"),
    FieldName.URGENT_CARE: _copay(_ER, "pbp_b4b_copay_amt_mc", "pbp_b4b_coins_pct_mc_min"),
    # Per day, first day interval only. Later intervals (days 6 to 90 and so on) are not read yet.
    FieldName.INPATIENT_STAY: PbpColumn(
        "pbp_b1a_inpat_hosp.txt",
        "pbp_b1a_copay_mcs_amt_int1_t1",
        coins_column="pbp_b1a_coins_mcs_pct_int1_t1",
    ),
    # Medicare-covered outpatient hospital services (9a1). CMS files one min and max for all of
    # them, so a plan that charges $0 for some services and $100 for surgery is a range.
    FieldName.OUTPATIENT_SURGERY: _copay(
        "pbp_b9_outpat_hosp.txt", "pbp_b9a_copay_ohs_amt", "pbp_b9a_coins_ohs_pct_min"
    ),
    FieldName.DRUG_DEDUCTIBLE: PbpColumn("pbp_mrx.txt", "mrx_alt_ded_amount"),
    FieldName.DRUG_TIER_1: PbpColumn(
        _TIER, "mrx_tier_rstd_copay_1m", tier="1", coins_column="mrx_tier_rstd_coins_1m"
    ),
    FieldName.DRUG_TIER_2: PbpColumn(
        _TIER, "mrx_tier_rstd_copay_1m", tier="2", coins_column="mrx_tier_rstd_coins_1m"
    ),
    FieldName.DRUG_TIER_3: PbpColumn(
        _TIER, "mrx_tier_rstd_copay_1m", tier="3", coins_column="mrx_tier_rstd_coins_1m"
    ),
    # Comprehensive dental maximum. A plan whose comprehensive dental is "covered under" the
    # preventive maximum (16c type 1) files one shared maximum under 16b instead.
    FieldName.DENTAL_ALLOWANCE: PbpColumn(
        _DENTAL,
        "pbp_b16c_maxplan_cmp_amt",
        period_column="pbp_b16c_maxplan_cmp_per",
        fallback=PbpColumn(
            _DENTAL,
            "pbp_b16b_maxplan_pv_amt",
            period_column="pbp_b16b_maxplan_pv_per",
            only_when=("pbp_b16c_maxplan_cmp_type", "1"),
        ),
    ),
    # OTC maximum in 13b, else the Section D combined benefit group that includes 13b (a card
    # shared with other benefits; the group name goes into the citation).
    FieldName.OTC_ALLOWANCE: PbpColumn(
        "pbp_b13_other_services.txt",
        "pbp_b13b_maxplan_amt",
        period_column="pbp_b13b_otc_maxplan_per",
        fallback=PbpColumn(_SECTION_D, "", combo_category="13b"),
    ),
}


@dataclass(frozen=True)
class PbpLayout:
    separator: str = "\t"
    contract: str = "pbp_a_hnumber"
    plan: str = "pbp_a_plan_identifier"
    segment: str = "segment_id"
    tier: str = "mrx_tier_id"
    fields: dict[FieldName, PbpColumn | None] = field(default_factory=lambda: _PBP_2026_FIELDS)


CROSSWALK_LAYOUTS: dict[int, CrosswalkLayout] = {2026: CrosswalkLayout(), 2027: CrosswalkLayout()}
LANDSCAPE_LAYOUTS: dict[int, LandscapeLayout] = {2026: LandscapeLayout(), 2027: LandscapeLayout()}
PBP_LAYOUTS: dict[int, PbpLayout] = {2026: PbpLayout(), 2027: PbpLayout()}
