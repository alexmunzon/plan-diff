from decimal import Decimal
from pathlib import Path

import pytest
from pdf_factory import make_plan_pdf

from plan_diff.classify import classify_pages, classify_pdf
from plan_diff.extract import (
    ALLOWANCES,
    DRUGS,
    FAMILIES,
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
    annualize,
)

PARSERS = {p.field: p for family in FAMILIES.values() for p in family}


def test_every_v1_field_has_exactly_one_parser() -> None:
    fields = [p.field for family in FAMILIES.values() for p in family]
    assert sorted(fields) == sorted(FieldName) and len(fields) == 15
    assert {p.field for p in DRUGS} == {
        FieldName.DRUG_DEDUCTIBLE,
        FieldName.DRUG_TIER_1,
        FieldName.DRUG_TIER_2,
        FieldName.DRUG_TIER_3,
    }
    assert {p.field for p in ALLOWANCES} == {FieldName.DENTAL_ALLOWANCE, FieldName.OTC_ALLOWANCE}


def test_spec_example_1_reads_all_15_fields_with_pages(tmp_path: Path) -> None:
    fake = make_plan_pdf(tmp_path)
    result = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    assert set(result.fields) == set(FieldName)
    assert result.review_items == ()
    for name, field in result.fields.items():
        assert field.citation.page == fake.field_pages[name], name
        assert field.confidence == 0.9
    assert fake.field_pages[FieldName.OTC_ALLOWANCE] == 2
    got = {n: (f.value, f.unit) for n, f in result.fields.items()}
    assert got[FieldName.DRUG_DEDUCTIBLE] == (Money(amount=Decimal(0)), Unit.PER_YEAR)
    assert got[FieldName.DRUG_TIER_1] == (Copay(amount=Decimal(0)), Unit.PER_PRESCRIPTION)
    assert got[FieldName.DRUG_TIER_2] == (Copay(amount=Decimal(5)), Unit.PER_PRESCRIPTION)
    assert got[FieldName.DRUG_TIER_3] == (Copay(amount=Decimal(47)), Unit.PER_PRESCRIPTION)
    assert got[FieldName.DENTAL_ALLOWANCE] == (Money(amount=Decimal(1500)), Unit.PER_YEAR)
    assert got[FieldName.OTC_ALLOWANCE] == (Money(amount=Decimal(50)), Unit.PER_QUARTER)


@pytest.mark.parametrize(
    ("field", "text", "value", "unit"),
    [
        (FieldName.DRUG_DEDUCTIBLE, "$0 deductible", Money(amount=Decimal(0)), Unit.PER_YEAR),
        (FieldName.DRUG_DEDUCTIBLE, "$545", Money(amount=Decimal(545)), Unit.PER_YEAR),
        (FieldName.DRUG_TIER_1, "$0 copay", Copay(amount=Decimal(0)), Unit.PER_PRESCRIPTION),
        (
            FieldName.DRUG_TIER_2,
            "25% coinsurance",
            Coinsurance(percent=Decimal(25)),
            Unit.PER_PRESCRIPTION,
        ),
        (FieldName.DRUG_TIER_3, "Not covered", NotCovered(), None),
        (
            FieldName.DENTAL_ALLOWANCE,
            "$1,500 per year dental",
            Money(amount=Decimal(1500)),
            Unit.PER_YEAR,
        ),
        (FieldName.DENTAL_ALLOWANCE, "$0", Money(amount=Decimal(0)), None),  # Review 2: no period
        (
            FieldName.OTC_ALLOWANCE,
            "$50 every quarter OTC",
            Money(amount=Decimal(50)),
            Unit.PER_QUARTER,
        ),
        (FieldName.OTC_ALLOWANCE, "$100 per month", Money(amount=Decimal(100)), Unit.PER_MONTH),
        (FieldName.OTC_ALLOWANCE, "Not covered", NotCovered(), None),
    ],
)
def test_each_parser_reads_its_formats(
    field: FieldName, text: str, value: object, unit: Unit | None
) -> None:
    parsed = parse_value(text, PARSERS[field])
    assert parsed is not None
    assert (parsed.value, parsed.unit, parsed.multiple) == (value, unit, False)


@pytest.mark.parametrize(
    "line",
    [
        "Tier 1: $0 copay",
        "Tier 1 (preferred generic): $0 copay",
        "Tier 1 preferred generic drugs $0 copay",
    ],
)
def test_tier_row_label_variants(line: str) -> None:
    pages = [line]
    result = extract_pages(pages, classify_pages(pages, document_id="d"))
    assert result.fields[FieldName.DRUG_TIER_1].value == Copay(amount=Decimal(0))
    assert FieldName.DRUG_TIER_2 not in result.fields  # "Tier 1" never reads as another tier


@pytest.mark.parametrize(
    "text",
    [
        "$47 copay (standard) / $42 (preferred)",
        "$42 copay (preferred) / $47 copay (standard)",
        "Preferred pharmacy: $42, standard pharmacy: $47",
    ],
)
def test_tier_with_preferred_and_standard_takes_standard(tmp_path: Path, text: str) -> None:
    fake = make_plan_pdf(tmp_path, values={FieldName.DRUG_TIER_3: text})
    result = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    got = result.fields[FieldName.DRUG_TIER_3]
    assert got.value == Copay(amount=Decimal(47))
    assert got.confidence == 0.6
    (item,) = result.review_items  # the rule is recorded, never silent
    assert item.kind is ReviewKind.CONFLICTING_VALUES
    assert "standard pharmacy" in item.reason


def test_tier_prefers_the_30_day_supply() -> None:
    parsed = parse_value(
        "$47 for a 30-day supply; $141 for a 90-day supply", PARSERS[FieldName.DRUG_TIER_3]
    )
    assert parsed is not None and parsed.value == Copay(amount=Decimal(47))
    assert parsed.picked == "30-day supply"


def test_comma_in_an_amount_is_not_a_split() -> None:
    parsed = parse_value(
        "$1,500 in-network / $500 out-of-network", PARSERS[FieldName.MOOP_IN_NETWORK]
    )
    assert parsed is not None and parsed.value == Money(amount=Decimal(1500))


def test_missing_tier_is_not_extracted(tmp_path: Path) -> None:
    fake = make_plan_pdf(tmp_path, omit=(FieldName.DRUG_TIER_2,))
    result = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    assert FieldName.DRUG_TIER_2 not in result.fields
    assert FieldName.DRUG_TIER_1 in result.fields and FieldName.DRUG_TIER_3 in result.fields
    (item,) = result.review_items
    assert (item.kind, item.field) == (ReviewKind.NOT_EXTRACTED, FieldName.DRUG_TIER_2)


def test_unreadable_allowance_is_not_a_guess(tmp_path: Path) -> None:
    values = {FieldName.DENTAL_ALLOWANCE: "Call the plan for details"}
    fake = make_plan_pdf(tmp_path, values=values)
    result = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    assert FieldName.DENTAL_ALLOWANCE not in result.fields
    (item,) = result.review_items
    assert item.kind is ReviewKind.NOT_EXTRACTED and "unreadable" in item.reason


@pytest.mark.parametrize(
    ("value", "unit", "yearly"),
    [
        (50, Unit.PER_QUARTER, "200"),
        (Decimal("100"), Unit.PER_MONTH, "1200"),
        (Decimal("1500.00"), Unit.PER_YEAR, "1500"),
        (Decimal("33.33"), Unit.PER_MONTH, "399.96"),
    ],
)
def test_annualize(value: Decimal | int, unit: Unit, yearly: str) -> None:
    got = annualize(value, unit)
    assert isinstance(got, Decimal) and got == Decimal(yearly)


def test_annualize_refuses_float_and_non_periods() -> None:
    assert annualize(50, Unit.PER_QUARTER) == 200
    with pytest.raises(ValueError, match="float"):
        annualize(50.0, Unit.PER_QUARTER)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="per_visit"):
        annualize(Decimal(5), Unit.PER_VISIT)


def test_unit_has_quarter() -> None:
    assert Unit("per_quarter") is Unit.PER_QUARTER


@pytest.mark.parametrize(
    "text", ["$300 every 6 months", "$300 twice a year", "$300 semiannually", "$300 semi-annual"]
)
def test_half_year_allowance(text: str) -> None:
    parsed = parse_value(text, PARSERS[FieldName.OTC_ALLOWANCE])
    assert parsed is not None and parsed.unit is Unit.PER_HALF_YEAR
    assert annualize(Decimal(300), Unit.PER_HALF_YEAR) == Decimal(600)


@pytest.mark.parametrize(
    ("text", "unit"),
    [("$1,500 annual maximum", Unit.PER_YEAR), ("$40 monthly", Unit.PER_MONTH)],
)
def test_plain_period_words(text: str, unit: Unit) -> None:
    parsed = parse_value(text, PARSERS[FieldName.DENTAL_ALLOWANCE])
    assert parsed is not None and parsed.unit is unit and parsed.unknown_period == ""


@pytest.mark.parametrize(
    "text", ["$80 every 2 months", "$2,000 every 2 years", "$75 bi-annual", "$60 bimonthly"]
)
def test_unknown_period_never_falls_back_to_a_year(tmp_path: Path, text: str) -> None:
    parsed = parse_value(text, PARSERS[FieldName.OTC_ALLOWANCE])
    assert parsed is not None and parsed.unit is None and parsed.unknown_period
    fake = make_plan_pdf(tmp_path, values={FieldName.OTC_ALLOWANCE: text})
    result = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    got = result.fields[FieldName.OTC_ALLOWANCE]
    assert isinstance(got.value, Money) and got.unit is None and got.confidence == 0.6
    (item,) = result.review_items
    assert (item.kind, item.field) == (ReviewKind.UNKNOWN_PERIOD, FieldName.OTC_ALLOWANCE)
    assert item.evidence[0].page == fake.field_pages[FieldName.OTC_ALLOWANCE]
    with pytest.raises(ValueError, match="cannot be made yearly"):
        annualize(got.value.amount, got.unit)  # the diff cannot annualize it
