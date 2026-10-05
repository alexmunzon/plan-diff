"""PR 8: year-over-year diff and the shop-again flag (SPEC decision 4, examples 1, 2, 3, 5)."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from plan_diff.cms.readers import read_crosswalk
from plan_diff.diff import CrosswalkRow, crosswalk_row_for, diff_plans
from plan_diff.models import (
    Citation,
    CitationMethod,
    Coinsurance,
    Copay,
    CrosswalkStatus,
    Direction,
    ExtractedField,
    FieldChange,
    FieldName,
    FieldValue,
    Money,
    NotCovered,
    PlanDiff,
    PlanRecord,
    ReviewKind,
    Severity,
    Unit,
    category_for,
)

CROSSWALK = Path(__file__).resolve().parents[3] / "fixtures" / "cms" / "crosswalk_2027.csv"
ALL = ("H9999-001", "H9999-002", "H9999-003", "H9999-004", "H9999-005", "H9998-010")
COUNTIES = ("Bexar", "Comal")


def field(name: FieldName, value: FieldValue, unit: Unit | None, year: int) -> ExtractedField:
    cite = Citation(document_id=f"sb-{year}", page=2, method=CitationMethod.RULE)
    return ExtractedField(name=name, value=value, unit=unit, citation=cite, confidence=0.9)


def plan(
    year: int,
    plan_id: str = "H9999-001",
    counties: tuple[str, ...] = COUNTIES,
    **values: tuple[FieldValue, Unit | None],
) -> PlanRecord:
    base: dict[str, tuple[FieldValue, Unit | None]] = {
        "monthly_premium": (Money(amount=Decimal("0")), Unit.PER_MONTH),
        "moop_in_network": (Money(amount=Decimal("4500")), Unit.PER_YEAR),
        "drug_deductible": (Money(amount=Decimal("0")), Unit.PER_YEAR),
        "pcp_copay": (Copay(amount=Decimal("0")), Unit.PER_VISIT),
        "dental_allowance": (Money(amount=Decimal("1000")), Unit.PER_YEAR),
    } | values
    fields = {FieldName(k): field(FieldName(k), v, u, year) for k, (v, u) in base.items()}
    return PlanRecord(
        plan_id=plan_id,
        year=year,
        carrier="Example Health Plan",
        plan_name="Example Plan",
        counties=counties,
        fields=fields,
        documents=(f"sb-{year}",),
    )


def renewal(plan_id: str = "H9999-001") -> CrosswalkRow:
    return CrosswalkRow(
        previous_plan_id=plan_id,
        current_plan_id=plan_id,
        status=CrosswalkStatus.CONTINUING,
        cms_status_label="Renewal Plan",
        source_row=1,
        document_id="crosswalk_2027.csv",
    )


def money(amount: str, unit: Unit = Unit.PER_MONTH) -> tuple[Money, Unit]:
    return Money(amount=Decimal(amount)), unit


def run(old: PlanRecord, new: PlanRecord | None, row: CrosswalkRow | None) -> PlanDiff:
    new_area = new.counties if new else ()
    return diff_plans(old, new, row, old.counties, new_area)


def by_field(diff: PlanDiff) -> dict[FieldName, Direction]:
    return {c.field: c.direction for c in diff.changes}


def xwalk(old_id: str) -> CrosswalkRow | None:
    return crosswalk_row_for(read_crosswalk(CROSSWALK, 2027, plan_ids=ALL), old_id, CROSSWALK.name)


def test_example_1_premium_0_to_25_flags() -> None:
    diff = run(plan(2026), plan(2027, monthly_premium=money("25")), renewal())
    assert by_field(diff)[FieldName.MONTHLY_PREMIUM] == Direction.UP
    assert diff.shop_again is True
    assert diff.reasons == ("premium up $25 a month",)


def test_example_2_consolidated_follows_crosswalk() -> None:
    row = xwalk("H9999-002")
    assert row is not None and row.status == CrosswalkStatus.CONSOLIDATED
    diff = run(plan(2026, "H9999-002"), plan(2027, "H9999-001"), row)
    assert diff.new_plan_id == "H9999-001"
    assert "plan consolidated into H9999-001" in diff.reasons
    assert not any("terminated" in r for r in diff.reasons)
    assert diff.shop_again is True


def test_example_3_terminated_with_crosswalk_evidence() -> None:
    row = xwalk("H9999-003")
    assert row is not None
    diff = run(plan(2026, "H9999-003"), None, row)
    assert diff.shop_again is True
    assert diff.reasons == ("plan terminated",)
    assert diff.new_plan_id is None and diff.changes == ()
    (cite,) = diff.evidence
    assert cite.method == CitationMethod.CMS
    assert cite.document_id == "crosswalk_2027.csv" and cite.page == 3
    assert cite.text == "Terminated/Non-renewed Plan"


def test_example_5_moop_up_500_reported_not_flagged() -> None:
    diff = run(plan(2026), plan(2027, moop_in_network=money("5000", Unit.PER_YEAR)), renewal())
    assert by_field(diff)[FieldName.MOOP_IN_NETWORK] == Direction.UP
    assert diff.shop_again is False and diff.reasons == ()


def test_missing_crosswalk_row_is_not_a_termination() -> None:
    assert xwalk("H9999-777") is None
    diff = run(plan(2026, "H9999-777"), None, None)
    assert diff.shop_again is None  # undecided
    assert diff.crosswalk_status is None and diff.reasons == ()
    (item,) = diff.review
    assert item.kind == ReviewKind.CROSSWALK_ROW_MISSING
    assert "crosswalk row missing" in item.reason


def test_missing_crosswalk_row_ignores_a_same_id_new_record() -> None:
    diff = run(plan(2026), plan(2027, monthly_premium=money("99")), None)
    assert diff.shop_again is None and diff.changes == ()


def test_undecided_diff_needs_a_review_item() -> None:
    with pytest.raises(ValidationError):
        PlanDiff(
            old_plan_id="H9999-001",
            new_plan_id=None,
            old_year=2026,
            new_year=2027,
            crosswalk_status=None,
            changes=(),
            shop_again=None,
            reasons=(),
        )


def test_decided_diff_needs_a_crosswalk_status() -> None:
    with pytest.raises(ValidationError):
        PlanDiff(
            old_plan_id="H9999-001",
            new_plan_id=None,
            old_year=2026,
            new_year=2027,
            crosswalk_status=None,
            changes=(),
            shop_again=False,
            reasons=(),
        )


@pytest.mark.parametrize(("premium", "flag"), [("19.99", False), ("20.00", True)])
def test_premium_threshold_edge(premium: str, flag: bool) -> None:
    diff = run(plan(2026), plan(2027, monthly_premium=money(premium)), renewal())
    assert diff.shop_again is flag
    if flag:
        assert diff.reasons == ("premium up $20 a month",)


@pytest.mark.parametrize(("moop", "flag"), [("5499", False), ("5500", True)])
def test_moop_threshold_edge(moop: str, flag: bool) -> None:
    diff = run(plan(2026), plan(2027, moop_in_network=money(moop, Unit.PER_YEAR)), renewal())
    assert diff.shop_again is flag
    if flag:
        assert diff.reasons == ("maximum out-of-pocket up $1,000",)


def test_drug_deductible_up_any_amount_flags() -> None:
    diff = run(plan(2026), plan(2027, drug_deductible=money("0.01", Unit.PER_YEAR)), renewal())
    assert diff.reasons == ("drug deductible up $0.01",)


def test_copay_to_coinsurance_not_comparable_and_no_flag() -> None:
    new = plan(2027, pcp_copay=(Coinsurance(percent=Decimal("20")), Unit.PER_VISIT))
    diff = run(plan(2026), new, renewal())
    assert by_field(diff)[FieldName.PCP_COPAY] == Direction.NOT_COMPARABLE
    assert diff.shop_again is False


def test_otc_quarterly_50_to_yearly_150_is_down() -> None:
    old = plan(2026, otc_allowance=money("50", Unit.PER_QUARTER))
    new = plan(2027, otc_allowance=money("150", Unit.PER_YEAR))
    diff = run(old, new, renewal())
    assert by_field(diff)[FieldName.OTC_ALLOWANCE] == Direction.DOWN
    assert diff.shop_again is False


def test_allowance_with_no_period_is_not_comparable() -> None:
    old = plan(2026, otc_allowance=(Money(amount=Decimal("50")), None))
    diff = run(old, plan(2027, otc_allowance=money("150", Unit.PER_YEAR)), renewal())
    assert by_field(diff)[FieldName.OTC_ALLOWANCE] == Direction.NOT_COMPARABLE


def test_unchanged_fields_are_same_and_listed() -> None:
    diff = run(plan(2026), plan(2027), renewal())
    assert set(by_field(diff).values()) == {Direction.SAME}
    assert len(diff.changes) == 5 and diff.shop_again is False


def test_benefit_now_not_covered_is_removed_and_flags() -> None:
    new = plan(2027, dental_allowance=(NotCovered(), None))
    diff = run(plan(2026), new, renewal())
    assert by_field(diff)[FieldName.DENTAL_ALLOWANCE] == Direction.REMOVED
    assert diff.reasons == ("benefit removed: dental allowance no longer covered",)
    assert diff.review == ()


def test_benefit_absent_in_new_year_goes_to_review_not_flag() -> None:
    # Absent may be an extraction miss: not comparable, a review item, and no flag.
    new = plan(2027)
    del new.fields[FieldName.DENTAL_ALLOWANCE]
    diff = run(plan(2026), new, renewal())
    assert by_field(diff)[FieldName.DENTAL_ALLOWANCE] == Direction.NOT_COMPARABLE
    assert diff.shop_again is False and diff.reasons == ()
    (item,) = diff.review
    assert item.kind == ReviewKind.NOT_EXTRACTED and item.field == FieldName.DENTAL_ALLOWANCE
    assert item.severity == Severity.MEDIUM and item.year == 2027
    assert item.evidence[0].document_id == "sb-2026"


def test_removed_needs_an_explicit_not_covered_value() -> None:
    old = field(FieldName.DENTAL_ALLOWANCE, Money(amount=Decimal("1000")), Unit.PER_YEAR, 2026)
    with pytest.raises(ValidationError):
        FieldChange(
            field=FieldName.DENTAL_ALLOWANCE,
            old=old,
            new=None,
            category=category_for(FieldName.DENTAL_ALLOWANCE),
            direction=Direction.REMOVED,
        )


def test_new_benefit_is_added_and_does_not_flag() -> None:
    old = plan(2026, otc_allowance=(NotCovered(), None))
    diff = run(old, plan(2027, otc_allowance=money("50", Unit.PER_QUARTER)), renewal())
    assert by_field(diff)[FieldName.OTC_ALLOWANCE] == Direction.ADDED
    assert diff.shop_again is False


def test_lost_county_flags_with_names() -> None:
    old, new = plan(2026), plan(2027, counties=("Bexar",))
    diff = diff_plans(old, new, renewal(), old.counties, new.counties)
    assert diff.reasons == ("service area lost 1 county: Comal",)


def test_service_area_reduced_status_flags() -> None:
    row = xwalk("H9998-010")
    assert row is not None
    diff = run(plan(2026, "H9998-010"), plan(2027, "H9998-010"), row)
    assert diff.reasons == ("service area reduced (CMS crosswalk)",)


def test_crosswalk_must_match_the_records() -> None:
    with pytest.raises(ValueError, match="crosswalk"):
        run(plan(2026), plan(2027, "H9999-002"), renewal())
    with pytest.raises(ValueError, match="no 2027 record"):
        run(plan(2026), None, renewal())
