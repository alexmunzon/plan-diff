from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pdf_factory import FakePdf, make_plan_pdf

from plan_diff.classify import classify_pages, classify_pdf
from plan_diff.extract import (
    COST_SHARING,
    ExtractionResult,
    extract_document,
    extract_pages,
    parse_value,
)
from plan_diff.models import (
    Coinsurance,
    Copay,
    FieldName,
    Money,
    NotCovered,
    ReviewKind,
    Unit,
)


def _extract(tmp_path: Path, **kwargs: Any) -> tuple[FakePdf, ExtractionResult]:
    fake = make_plan_pdf(tmp_path, **kwargs)
    result = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    return fake, result


@pytest.mark.parametrize(("year", "premium"), [(2026, "0.00"), (2027, "25.00")])
def test_spec_example_1_premium_and_pages(tmp_path: Path, year: int, premium: str) -> None:
    values = {FieldName.MONTHLY_PREMIUM: f"${premium.split('.')[0]} per month"}
    fake, result = _extract(tmp_path, year=year, values=values)
    assert set(result.fields) == set(FieldName)  # PR 6 reads all 15
    assert result.review_items == ()
    got = result.fields[FieldName.MONTHLY_PREMIUM]
    assert got.value == Money(amount=Decimal(premium))
    assert got.unit is Unit.PER_MONTH
    for name, field in result.fields.items():
        assert field.citation.page == fake.field_pages[name]
        assert field.citation.document_id == "doc"
        assert field.citation.method == "rule"
        assert field.confidence == 0.9
    assert result.fields[FieldName.MOOP_IN_NETWORK].value == Money(amount=Decimal("3400"))
    assert result.fields[FieldName.SPECIALIST_COPAY].value == Copay(amount=Decimal("45"))
    assert result.fields[FieldName.SPECIALIST_COPAY].unit is Unit.PER_VISIT
    inpatient = result.fields[FieldName.INPATIENT_STAY]
    assert (inpatient.value, inpatient.unit) == (Copay(amount=Decimal("295")), Unit.PER_DAY)
    assert result.fields[FieldName.OUTPATIENT_SURGERY].value == Coinsurance(percent=Decimal(20))


@pytest.mark.parametrize(
    ("field", "text", "value", "unit"),
    [
        (FieldName.MONTHLY_PREMIUM, "$0", Money(amount=Decimal(0)), Unit.PER_MONTH),
        (FieldName.MEDICAL_DEDUCTIBLE, "$1,500", Money(amount=Decimal(1500)), Unit.PER_YEAR),
        (
            FieldName.MOOP_IN_NETWORK,
            "$8,850.50 per year",
            Money(amount=Decimal("8850.5")),
            Unit.PER_YEAR,
        ),
        (FieldName.PCP_COPAY, "$0 copay", Copay(amount=Decimal(0)), Unit.PER_VISIT),
        (FieldName.SPECIALIST_COPAY, "$45 copay", Copay(amount=Decimal(45)), Unit.PER_VISIT),
        (
            FieldName.EMERGENCY_ROOM,
            "20% coinsurance",
            Coinsurance(percent=Decimal(20)),
            Unit.PER_VISIT,
        ),
        (FieldName.URGENT_CARE, "Not covered", NotCovered(), None),
        (
            FieldName.INPATIENT_STAY,
            "$395 per day for days 1 to 5; $0 per day for days 6 to 90",
            Copay(amount=Decimal(395)),
            Unit.PER_DAY,
        ),
        (FieldName.OUTPATIENT_SURGERY, "$250 copay", Copay(amount=Decimal(250)), Unit.PER_VISIT),
    ],
)
def test_each_parser_reads_its_formats(
    field: FieldName, text: str, value: object, unit: Unit | None
) -> None:
    parsed = parse_value(text, next(p for p in COST_SHARING if p.field is field))
    assert parsed is not None
    assert (parsed.value, parsed.unit, parsed.multiple) == (value, unit, False)


def test_coinsurance_is_not_a_copay() -> None:
    parser = next(p for p in COST_SHARING if p.field is FieldName.SPECIALIST_COPAY)
    coins, copay = parse_value("20% coinsurance", parser), parse_value("$20 copay", parser)
    assert coins is not None and copay is not None
    assert isinstance(coins.value, Coinsurance) and isinstance(copay.value, Copay)
    assert coins.value != copay.value


@pytest.mark.parametrize(
    ("text", "amount"),
    [("$0 or $40", "0"), ("$40 out of network, $10 in network", "10")],
)
def test_two_values_in_one_cell_take_in_network_or_first(
    tmp_path: Path, text: str, amount: str
) -> None:
    _, result = _extract(tmp_path, values={FieldName.PCP_COPAY: text})
    got = result.fields[FieldName.PCP_COPAY]
    assert got.value == Copay(amount=Decimal(amount))
    assert got.confidence == 0.6
    assert got.citation.text == text
    (item,) = result.review_items  # the choice is recorded, never silent
    assert item.kind is ReviewKind.CONFLICTING_VALUES and "one cell" in item.reason


def test_not_covered_from_a_pdf(tmp_path: Path) -> None:
    _, result = _extract(tmp_path, values={FieldName.URGENT_CARE: "Not covered"})
    got = result.fields[FieldName.URGENT_CARE]
    assert got.value == NotCovered() and got.unit is None


def test_missing_field_is_absent_and_goes_to_review(tmp_path: Path) -> None:
    _, result = _extract(tmp_path, omit=(FieldName.EMERGENCY_ROOM,))
    assert FieldName.EMERGENCY_ROOM not in result.fields
    (item,) = result.review_items
    assert item.kind is ReviewKind.NOT_EXTRACTED
    assert item.field is FieldName.EMERGENCY_ROOM
    assert (item.plan_id, item.year) == ("H9999-001", 2026)


def test_unreadable_value_is_not_a_guess(tmp_path: Path) -> None:
    _, result = _extract(tmp_path, values={FieldName.URGENT_CARE: "See your Evidence of Coverage"})
    assert FieldName.URGENT_CARE not in result.fields
    (item,) = result.review_items
    assert item.kind is ReviewKind.NOT_EXTRACTED
    assert item.evidence[0].page == 1 and "unreadable" in item.reason


def test_two_values_on_two_pages_lower_confidence_and_cite_both(tmp_path: Path) -> None:
    fake, result = _extract(tmp_path, extra_rows=((2, "Specialist visit", "$50 per visit"),))
    got = result.fields[FieldName.SPECIALIST_COPAY]
    assert got.value == Copay(amount=Decimal(45))  # first page kept, never silently replaced
    assert got.confidence == 0.3
    (item,) = result.review_items
    assert item.kind is ReviewKind.CONFLICTING_VALUES
    assert [c.page for c in item.evidence] == [fake.field_pages[FieldName.SPECIALIST_COPAY], 2]
    assert "$45" in item.reason and "$50" in item.reason


def test_same_value_repeated_is_not_a_conflict(tmp_path: Path) -> None:
    _, result = _extract(tmp_path, extra_rows=((2, "Specialist visit", "$45 per visit"),))
    assert result.fields[FieldName.SPECIALIST_COPAY].confidence == 0.9
    assert result.review_items == ()


def test_drug_deductible_does_not_read_as_medical_deductible() -> None:
    pages = ["Prescription drug deductible $590 per year\nMedical deductible $0 per year"]
    result = extract_pages(pages, classify_pages(pages, document_id="d"))
    assert result.fields[FieldName.MEDICAL_DEDUCTIBLE].value == Money(amount=Decimal(0))
    assert result.fields[FieldName.DRUG_DEDUCTIBLE].value == Money(amount=Decimal(590))
