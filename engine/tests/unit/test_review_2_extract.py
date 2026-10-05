"""Review 2 extraction fixes: an unreadable or ambiguous cell never becomes a confident value."""

from decimal import Decimal

import pytest

from plan_diff.classify import classify_pages
from plan_diff.extract import FAMILIES, ExtractionResult, extract_pages, parse_value
from plan_diff.models import (
    Coinsurance,
    Copay,
    FieldName,
    Money,
    NotCovered,
    ReviewKind,
    Severity,
    Unit,
)

PARSERS = {p.field: p for family in FAMILIES.values() for p in family}


def _run(*pages: str) -> ExtractionResult:
    return extract_pages(list(pages), classify_pages(list(pages), document_id="d"))


def _items(result: ExtractionResult, field: FieldName) -> list[ReviewKind]:
    return [i.kind for i in result.review_items if i.field is field]


# F2: period words set the unit only for allowances; premium is per month unless it says otherwise.


def test_f2_moop_ignores_a_period_word_about_the_premium() -> None:
    parsed = parse_value(
        "$3,400 (does not include your monthly premium)", PARSERS[FieldName.MOOP_IN_NETWORK]
    )
    assert parsed is not None
    assert (parsed.value, parsed.unit) == (Money(amount=Decimal(3400)), Unit.PER_YEAR)


def test_f2_copay_ignores_an_annual_limit_note() -> None:
    parsed = parse_value(
        "$40 copay (annual limit of 12 visits)", PARSERS[FieldName.SPECIALIST_COPAY]
    )
    assert parsed is not None
    assert (parsed.value, parsed.unit) == (Copay(amount=Decimal(40)), Unit.PER_VISIT)


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("$25 (includes your annual dental benefit)", Unit.PER_MONTH),
        ("$25 per month", Unit.PER_MONTH),
        ("$300 per year", Unit.PER_YEAR),
    ],
)
def test_f2_premium_is_per_month_unless_it_says_so_itself(text: str, unit: Unit) -> None:
    parsed = parse_value(text, PARSERS[FieldName.MONTHLY_PREMIUM])
    assert parsed is not None and parsed.unit is unit


@pytest.mark.parametrize(
    ("field", "text", "unit"),
    [
        (FieldName.SPECIALIST_COPAY, "$40 copay every quarter", Unit.PER_VISIT),
        (FieldName.URGENT_CARE, "$40 a year", Unit.PER_VISIT),
        (FieldName.DRUG_TIER_1, "$5 per month supply", Unit.PER_PRESCRIPTION),
        (FieldName.DRUG_TIER_1, "$5 per prescription", Unit.PER_PRESCRIPTION),
        (FieldName.INPATIENT_STAY, "$500 per stay", Unit.PER_STAY),
    ],
)
def test_f2_other_fields_take_only_cost_units(field: FieldName, text: str, unit: Unit) -> None:
    parsed = parse_value(text, PARSERS[field])
    assert parsed is not None and parsed.unit is unit


# F4: a label line with no value never takes the next row's value.


def test_f4_empty_label_line_does_not_steal_the_next_row() -> None:
    result = _run("Specialist visit\nEmergency room $90")
    assert FieldName.SPECIALIST_COPAY not in result.fields
    assert ReviewKind.NOT_EXTRACTED in _items(result, FieldName.SPECIALIST_COPAY)
    assert result.fields[FieldName.EMERGENCY_ROOM].value == Copay(amount=Decimal(90))
    assert result.fields[FieldName.EMERGENCY_ROOM].confidence == 0.9


def test_f4_wrapped_value_on_the_next_line_still_reads() -> None:
    result = _run("Specialist visit\n$45 per visit")
    assert result.fields[FieldName.SPECIALIST_COPAY].value == Copay(amount=Decimal(45))


# F5: an unreadable hit plus a readable one is a conflict; drug-section lines stay out of medical.


def test_f5_unreadable_plus_readable_is_a_conflict() -> None:
    result = _run("Medical deductible None", "Deductible $250")
    got = result.fields.get(FieldName.MEDICAL_DEDUCTIBLE)
    assert got is not None and got.confidence == 0.3
    assert ReviewKind.CONFLICTING_VALUES in _items(result, FieldName.MEDICAL_DEDUCTIBLE)
    (item,) = [i for i in result.review_items if i.field is FieldName.MEDICAL_DEDUCTIBLE]
    assert "None" in item.reason and "$250" in item.reason


def test_f5_drug_section_deductible_never_reads_as_medical() -> None:
    result = _run("Medical deductible None\nPrescription drug benefits\nDeductible $250")
    assert FieldName.MEDICAL_DEDUCTIBLE not in result.fields
    assert _items(result, FieldName.MEDICAL_DEDUCTIBLE) == [ReviewKind.NOT_EXTRACTED]


def test_f5_medical_section_after_drug_section_reads_again() -> None:
    result = _run("Part D drug coverage\nTier 1 $0\nMedical benefits\nDeductible $500")
    assert result.fields[FieldName.MEDICAL_DEDUCTIBLE].value == Money(amount=Decimal(500))
    assert result.fields[FieldName.MEDICAL_DEDUCTIBLE].confidence == 0.9


# F8: "not covered" is read before amounts.


def test_f8_not_covered_before_the_percent() -> None:
    parsed = parse_value("Not covered (you pay 100%)", PARSERS[FieldName.URGENT_CARE])
    assert parsed is not None
    assert (parsed.value, parsed.unit, parsed.multiple) == (NotCovered(), None, False)


def test_f8_not_covered_beside_an_amount_is_two_values() -> None:
    parsed = parse_value("$40 copay; not covered", PARSERS[FieldName.URGENT_CARE])
    assert parsed is not None and parsed.multiple


# F9: inpatient applies the in-network rule first; any day range means per day.


def test_f9_in_network_before_day_range() -> None:
    text = "Out-of-network: 40%... In-network: $295 per day for days 1 to 5"
    parsed = parse_value(text, PARSERS[FieldName.INPATIENT_STAY])
    assert parsed is not None
    assert (parsed.value, parsed.unit) == (Copay(amount=Decimal(295)), Unit.PER_DAY)


def test_f9_day_range_means_per_day() -> None:
    parsed = parse_value("Days 1 to 5: $295", PARSERS[FieldName.INPATIENT_STAY])
    assert parsed is not None
    assert (parsed.value, parsed.unit) == (Copay(amount=Decimal(295)), Unit.PER_DAY)


# F10: the unit comes from the chosen value's own text; an allowance with no period is not a year.


def test_f10_unit_from_the_chosen_value_only() -> None:
    parsed = parse_value("$50 ($200 a year)", PARSERS[FieldName.OTC_ALLOWANCE])
    assert parsed is not None and parsed.value == Money(amount=Decimal(50))
    assert parsed.unit is None and parsed.unknown_period


@pytest.mark.parametrize("text", ["$0", "$1,500"])
def test_f10_allowance_with_no_period_has_no_unit(text: str) -> None:
    parsed = parse_value(text, PARSERS[FieldName.DENTAL_ALLOWANCE])
    assert parsed is not None and parsed.unit is None and parsed.unknown_period
    result = _run(f"Dental allowance {text}")
    got = result.fields[FieldName.DENTAL_ALLOWANCE]
    assert got.unit is None and got.confidence == 0.6
    assert ReviewKind.UNKNOWN_PERIOD in _items(result, FieldName.DENTAL_ALLOWANCE)


# F11: footnote markers never merge into the number.


@pytest.mark.parametrize("text", ["$45¹", "$45*", "$45†"])
def test_f11_known_footnote_markers_are_stripped(text: str) -> None:
    parsed = parse_value(text, PARSERS[FieldName.SPECIALIST_COPAY])
    assert parsed is not None and parsed.value == Copay(amount=Decimal(45))
    assert parsed.ambiguous == ""


@pytest.mark.parametrize("text", ["$45 1", "$1,5001", "$45.501"])
def test_f11_ambiguous_digit_lowers_confidence(text: str) -> None:
    parsed = parse_value(text, PARSERS[FieldName.SPECIALIST_COPAY])
    assert parsed is not None and parsed.ambiguous
    result = _run(f"Specialist visit {text}")
    got = result.fields[FieldName.SPECIALIST_COPAY]
    assert got.confidence == 0.6
    assert ReviewKind.CONFLICTING_VALUES in _items(result, FieldName.SPECIALIST_COPAY)


def test_f11_superscript_from_a_pdf_line() -> None:
    result = _run("Specialist visit $45¹ per visit")
    got = result.fields[FieldName.SPECIALIST_COPAY]
    assert (got.value, got.confidence) == (Copay(amount=Decimal(45)), 0.9)


def test_coinsurance_still_reads() -> None:
    parsed = parse_value("20% coinsurance", PARSERS[FieldName.EMERGENCY_ROOM])
    assert parsed is not None and parsed.value == Coinsurance(percent=Decimal(20))


# Coordinator follow-up: an explicitly labeled pick is 0.85, a "first value" pick stays 0.6.


@pytest.mark.parametrize(
    "line",
    [
        "Maximum out-of-pocket $3,400 in-network / $6,700 out-of-network",
        "Maximum out-of-pocket Out-of-network: $6,700, In-network: $3,400",
    ],
)
def test_labeled_in_network_pick_is_085_with_a_review_item(line: str) -> None:
    result = _run(line)
    got = result.fields[FieldName.MOOP_IN_NETWORK]
    assert (got.value, got.confidence) == (Money(amount=Decimal(3400)), 0.85)
    (item,) = [i for i in result.review_items if i.field is FieldName.MOOP_IN_NETWORK]
    assert item.kind is ReviewKind.CONFLICTING_VALUES and item.severity is Severity.LOW
    assert "explicitly labeled in-network" in item.reason


@pytest.mark.parametrize(
    "line",
    [
        "Monthly plan premium $25 or $40",
        "Monthly plan premium $25 copay $40 in-network",  # marker not next to the chosen value
    ],
)
def test_unlabeled_first_pick_stays_06(line: str) -> None:
    result = _run(line)
    got = result.fields[FieldName.MONTHLY_PREMIUM]
    assert (got.value, got.confidence) == (Money(amount=Decimal(25)), 0.6)
    (item,) = [i for i in result.review_items if i.field is FieldName.MONTHLY_PREMIUM]
    assert "explicitly labeled" not in item.reason
