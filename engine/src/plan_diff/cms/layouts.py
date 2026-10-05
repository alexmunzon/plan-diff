"""Per-year column layouts for CMS public files. A layout change between years is data, not code.

Column names are UNCONFIRMED until the real files are downloaded (Alex approves the list first).
They come from the PBP, Landscape, and Crosswalk naming CMS has used in past years; see
docs/cms-fields.md for the open questions. 2027 starts as a copy of 2026: edit only what differs.
"""

from dataclasses import dataclass, field

from plan_diff.models import FieldName


@dataclass(frozen=True)
class CrosswalkLayout:
    separator: str = ","
    previous_contract: str = "PREVIOUS_CONTRACT_ID"
    previous_plan: str = "PREVIOUS_PLAN_ID"
    previous_segment: str = "PREVIOUS_SEGMENT_ID"
    current_contract: str = "CURRENT_CONTRACT_ID"
    current_plan: str = "CURRENT_PLAN_ID"
    current_segment: str = "CURRENT_SEGMENT_ID"
    status: str = "STATUS"


@dataclass(frozen=True)
class LandscapeLayout:
    separator: str = ","
    contract: str = "Contract ID"
    plan: str = "Plan ID"
    segment: str = "Segment ID"
    organization: str = "Organization Name"
    plan_name: str = "Plan Name"
    state: str = "State Territory Name"
    county: str = "County Name"
    premium: str = "Monthly Consolidated Premium (Includes Part C + D)"


@dataclass(frozen=True)
class PbpColumn:
    """Where one field lives in the PBP: a table file, a column, and for tiered tables a tier id."""

    file: str
    column: str
    tier: str | None = None


_PBP_2026_FIELDS: dict[FieldName, PbpColumn | None] = {
    # Not read from PBP: Section D holds only the Part C piece. The Landscape holds the
    # consolidated Part C + D premium that a Summary of Benefits quotes.
    FieldName.MONTHLY_PREMIUM: None,
    FieldName.MEDICAL_DEDUCTIBLE: PbpColumn("pbp_Section_D.txt", "pbp_d_ann_deduct_amt"),
    FieldName.MOOP_IN_NETWORK: PbpColumn("pbp_Section_D.txt", "pbp_d_out_pocket_amt"),
    FieldName.PCP_COPAY: PbpColumn("pbp_b7_health_prof.txt", "pbp_b7a_copay_amt_mc_min"),
    FieldName.SPECIALIST_COPAY: PbpColumn("pbp_b7_health_prof.txt", "pbp_b7d_copay_amt_mc_min"),
    FieldName.EMERGENCY_ROOM: PbpColumn("pbp_b4_emerg_urgent.txt", "pbp_b4a_copay_amt_mc_min"),
    FieldName.URGENT_CARE: PbpColumn("pbp_b4_emerg_urgent.txt", "pbp_b4b_copay_amt_mc_min"),
    # Per day, first day interval only. Later intervals (days 6 to 90 and so on) are not read yet.
    FieldName.INPATIENT_STAY: PbpColumn("pbp_b1a_inpat_hosp.txt", "pbp_b1a_copay_mcs_amt_int1_t1"),
    FieldName.OUTPATIENT_SURGERY: PbpColumn("pbp_b9a_outpat_hosp.txt", "pbp_b9a_copay_ohs_amt_min"),
    FieldName.DRUG_DEDUCTIBLE: PbpColumn("pbp_mrx.txt", "mrx_alt_ded_amount"),
    FieldName.DRUG_TIER_1: PbpColumn("pbp_mrx_tier.txt", "mrx_tier_rstd_copay_1m", tier="1"),
    FieldName.DRUG_TIER_2: PbpColumn("pbp_mrx_tier.txt", "mrx_tier_rstd_copay_1m", tier="2"),
    FieldName.DRUG_TIER_3: PbpColumn("pbp_mrx_tier.txt", "mrx_tier_rstd_copay_1m", tier="3"),
    FieldName.DENTAL_ALLOWANCE: PbpColumn("pbp_b16_dental.txt", "pbp_b16c_maxplan_amt"),
    FieldName.OTC_ALLOWANCE: PbpColumn("pbp_b13_other_services.txt", "pbp_b13b_maxplan_amt"),
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
