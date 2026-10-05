"""Review 2: the shop-again flag is never confidently wrong (F1, F3, F6, F7, F12)."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_diff import money, plan, renewal, run

from plan_diff.cms import read_landscape, read_pbp
from plan_diff.diff import diff_plans, same_county
from plan_diff.models import (
    Citation,
    CitationMethod,
    Copay,
    Direction,
    ExtractedField,
    FieldChange,
    FieldName,
    Money,
    PlanDiff,
    PlanRecord,
    ReviewKind,
    Severity,
    Unit,
    ValidationResult,
    Verdict,
    category_for,
)
from plan_diff.validate import cms_values_for

F = FieldName
CMS = Path(__file__).resolve().parents[3] / "fixtures" / "cms"


def _uncertain(diff: PlanDiff) -> dict[FieldName | None, str]:
    return {
        i.field: i.reason
        for i in diff.review
        if i.kind == ReviewKind.SHOP_AGAIN_UNCERTAIN and i.severity == Severity.HIGH
    }


def _without(record: PlanRecord, name: FieldName) -> PlanRecord:
    return record.model_copy(
        update={"fields": {k: v for k, v in record.fields.items() if k != name}}
    )


def _with_confidence(record: PlanRecord, name: FieldName, confidence: float) -> PlanRecord:
    fields = dict(record.fields)
    fields[name] = fields[name].model_copy(update={"confidence": confidence})
    return record.model_copy(update={"fields": fields})


def _mismatch(record: PlanRecord, name: FieldName, cms: str) -> ValidationResult:
    pdf = record.fields[name]
    return ValidationResult(
        plan_id=record.plan_id,
        year=record.year,
        field=name,
        pdf_value=pdf.value,
        cms_value=Money(amount=Decimal(cms)),
        verdict=Verdict.MISMATCH,
        pdf_citation=pdf.citation,
        cms_citation=Citation(document_id="pbp_b1a.txt", page=4, method=CitationMethod.CMS),
        pdf_unit=pdf.unit,
        cms_unit=pdf.unit,
        reason="values differ",
    )


# F1 (Blocker): a unit change on a threshold field used to give shop_again False with no review.


def test_f1_reviewer_probe_unit_changes_are_undecided_not_false() -> None:
    old = plan(2026, moop_in_network=money("3400", Unit.PER_YEAR))
    new = plan(
        2027,
        moop_in_network=money("8850", Unit.PER_MONTH),
        monthly_premium=money("45", Unit.PER_YEAR),
    )
    diff = run(old, new, renewal())
    assert diff.shop_again is None
    assert diff.reasons == ()
    found = _uncertain(diff)
    assert set(found) == {F.MOOP_IN_NETWORK, F.MONTHLY_PREMIUM}
    assert "maximum out-of-pocket" in found[F.MOOP_IN_NETWORK]
    assert "per month" in found[F.MOOP_IN_NETWORK] and "per year" in found[F.MOOP_IN_NETWORK]
    assert diff.changes  # the comparison page still shows every field


def test_f1_same_wrong_unit_both_years_is_undecided() -> None:
    old = plan(2026, monthly_premium=money("0", Unit.PER_YEAR))
    new = plan(2027, monthly_premium=money("10", Unit.PER_YEAR))
    diff = run(old, new, renewal())
    assert diff.shop_again is None and F.MONTHLY_PREMIUM in _uncertain(diff)


def test_f1_confident_trigger_still_flags_with_the_uncertain_field_listed() -> None:
    old = plan(2026, moop_in_network=money("3400", Unit.PER_YEAR))
    new = plan(2027, moop_in_network=money("8850", Unit.PER_MONTH), monthly_premium=money("25"))
    diff = run(old, new, renewal())
    assert diff.shop_again is True
    assert diff.reasons == ("premium up $25 a month",)
    assert set(_uncertain(diff)) == {F.MOOP_IN_NETWORK}


def test_f1_termination_still_flags() -> None:
    from test_diff import xwalk

    row = xwalk("H9999-003")
    assert row is not None
    diff = run(plan(2026, "H9999-003", moop_in_network=money("1", Unit.PER_DAY)), None, row)
    assert diff.shop_again is True and diff.reasons == ("plan terminated",)


def test_f1_model_refuses_false_with_an_uncertain_item() -> None:
    diff = run(plan(2026), plan(2027, monthly_premium=money("5", Unit.PER_YEAR)), renewal())
    data = diff.model_dump() | {"shop_again": False}
    with pytest.raises(ValidationError, match="undecided"):
        PlanDiff.model_validate(data)


# F3 (High): validation results and each field's confidence.


def test_f3_low_confidence_threshold_field_is_undecided() -> None:
    new = _with_confidence(
        plan(2027, moop_in_network=money("4600", Unit.PER_YEAR)), F.MOOP_IN_NETWORK, 0.6
    )
    diff = run(plan(2026), new, renewal())
    assert diff.shop_again is None
    assert "confidence 0.6" in _uncertain(diff)[F.MOOP_IN_NETWORK]


def test_f3_low_confidence_last_year_counts_too() -> None:
    old = _with_confidence(plan(2026), F.DRUG_DEDUCTIBLE, 0.3)
    diff = run(old, plan(2027), renewal())
    assert diff.shop_again is None and F.DRUG_DEDUCTIBLE in _uncertain(diff)


def test_f3_confidence_at_the_floor_is_trusted() -> None:
    new = _with_confidence(plan(2027), F.MOOP_IN_NETWORK, 0.7)
    assert run(plan(2026), new, renewal()).shop_again is False


def test_f3_cms_mismatch_makes_the_field_undecided() -> None:
    old, new = plan(2026), plan(2027, monthly_premium=money("10"))
    diff = diff_plans(
        old,
        new,
        renewal(),
        old.counties,
        new.counties,
        validation=[_mismatch(new, F.MONTHLY_PREMIUM, "40")],
    )
    assert diff.shop_again is None
    item = next(i for i in diff.review if i.field == F.MONTHLY_PREMIUM)
    assert item.severity == Severity.HIGH and "CMS" in item.reason
    assert any(c.method == CitationMethod.CMS for c in item.evidence)


def test_f3_cms_mismatch_hides_a_threshold_rise() -> None:
    # The PDF says the premium rose $25, CMS disagrees: the rise is not a confident reason.
    old, new = plan(2026), plan(2027, monthly_premium=money("25"))
    diff = diff_plans(
        old,
        new,
        renewal(),
        old.counties,
        new.counties,
        validation=[_mismatch(new, F.MONTHLY_PREMIUM, "0")],
    )
    assert diff.shop_again is None and diff.reasons == ()


def test_f3_mismatch_for_another_plan_or_a_match_is_ignored() -> None:
    old, new = plan(2026), plan(2027)
    other = _mismatch(plan(2027, "H9999-002"), F.MONTHLY_PREMIUM, "40")
    diff = diff_plans(old, new, renewal(), old.counties, new.counties, validation=[other])
    assert diff.shop_again is False


def test_f3_removed_benefit_with_a_cms_mismatch_is_not_a_reason() -> None:
    from plan_diff.models import NotCovered

    old, new = plan(2026), plan(2027, dental_allowance=(NotCovered(), None))
    bad = _mismatch(new, F.DENTAL_ALLOWANCE, "1000").model_copy(update={"cms_unit": None})
    diff = diff_plans(old, new, renewal(), old.counties, new.counties, validation=[bad])
    assert diff.reasons == () and diff.shop_again is None
    assert F.DENTAL_ALLOWANCE in _uncertain(diff)


# F6 (Medium): a field missing last year is not a silent ADDED.


def test_f6_missing_last_year_is_not_comparable_with_review() -> None:
    old = plan(2026)
    diff = run(old, plan(2027, otc_allowance=money("50", Unit.PER_QUARTER)), renewal())
    change = next(c for c in diff.changes if c.field == F.OTC_ALLOWANCE)
    assert change.direction == Direction.NOT_COMPARABLE
    item = next(i for i in diff.review if i.field == F.OTC_ALLOWANCE)
    assert item.kind == ReviewKind.NOT_EXTRACTED and item.year == 2026
    assert diff.shop_again is False  # not a threshold field


def test_f6_threshold_field_missing_last_year_is_undecided() -> None:
    diff = run(_without(plan(2026), F.MONTHLY_PREMIUM), plan(2027), renewal())
    assert diff.shop_again is None and F.MONTHLY_PREMIUM in _uncertain(diff)


def test_f6_threshold_field_missing_this_year_is_undecided() -> None:
    diff = run(plan(2026), _without(plan(2027), F.MOOP_IN_NETWORK), renewal())
    assert diff.shop_again is None and F.MOOP_IN_NETWORK in _uncertain(diff)


def test_f6_threshold_field_missing_both_years_is_undecided() -> None:
    diff = run(
        _without(plan(2026), F.DRUG_DEDUCTIBLE), _without(plan(2027), F.DRUG_DEDUCTIBLE), renewal()
    )
    assert diff.shop_again is None and F.DRUG_DEDUCTIBLE in _uncertain(diff)


def test_f6_added_with_no_old_value_is_refused() -> None:
    new = ExtractedField(
        name=F.PCP_COPAY,
        value=Copay(amount=Decimal("5")),
        unit=Unit.PER_VISIT,
        citation=Citation(document_id="sb-2027", page=2, method=CitationMethod.RULE),
        confidence=0.9,
    )
    with pytest.raises(ValidationError):
        FieldChange(
            field=F.PCP_COPAY,
            old=None,
            new=new,
            category=category_for(F.PCP_COPAY),
            direction=Direction.ADDED,
        )


# F7 (Medium): counties are normalized; an empty list never means "lost every county".


@pytest.mark.parametrize("name", ["Bexar County", "BEXAR", "Bexar", " bexar  county. "])
def test_f7_county_names_normalize(name: str) -> None:
    assert same_county(name, "Bexar")


def test_f7_spelling_differences_are_not_a_lost_county() -> None:
    old, new = (
        plan(2026, counties=("Bexar County", "Comal")),
        plan(2027, counties=("BEXAR", "comal county")),
    )
    diff = diff_plans(old, new, renewal(), old.counties, new.counties)
    assert diff.shop_again is False


def test_f7_real_loss_still_names_the_county() -> None:
    old, new = (
        plan(2026, counties=("Bexar County", "Comal County")),
        plan(2027, counties=("bexar",)),
    )
    diff = diff_plans(old, new, renewal(), old.counties, new.counties)
    assert diff.reasons == ("service area lost 1 county: Comal County",)


@pytest.mark.parametrize(("before", "after"), [(("Bexar",), ()), ((), ("Bexar",)), ((), ())])
def test_f7_empty_county_list_is_undecided(before: tuple[str, ...], after: tuple[str, ...]) -> None:
    diff = diff_plans(plan(2026), plan(2027), renewal(), before, after)
    assert diff.shop_again is None and diff.reasons == ()
    assert None in _uncertain(diff) and "service area" in _uncertain(diff)[None]


# F12 (Low): CMS citations carry the plan year and the real file name.


def test_f12_cms_citations_name_year_and_file() -> None:
    pbp = read_pbp(CMS / "pbp_2026", 2026, plan_ids=["H9999-001"])
    land = read_landscape(CMS / "landscape_2026.csv", 2026, plan_ids=["H9999-001"])
    cms = cms_values_for("H9999-001", pbp=pbp, landscape=land, landscape_file="landscape_2026.csv")
    spec = cms[F.SPECIALIST_COPAY].citation
    assert spec.document_id == "pbp_b7_health_prof.txt"
    assert spec.text is not None and "2026" in spec.text and "pbp_b7_health_prof.txt" in spec.text
    prem = cms[F.MONTHLY_PREMIUM].citation
    assert prem.document_id == "landscape_2026.csv"
    assert prem.text is not None and "2026" in prem.text


def test_f12_landscape_file_name_is_required() -> None:
    pbp = read_pbp(CMS / "pbp_2026", 2026, plan_ids=["H9999-001"])
    land = read_landscape(CMS / "landscape_2026.csv", 2026, plan_ids=["H9999-001"])
    with pytest.raises(ValueError, match="landscape_file"):
        cms_values_for("H9999-001", pbp=pbp, landscape=land)
